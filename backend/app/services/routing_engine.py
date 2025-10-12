from datetime import datetime, timezone
from typing import Optional, List, Dict, Union, Tuple, Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.models.models import Provider, RateCard, RoutingRule
from app.schemas.routing_rules import RoutingRuleActions
from app.services.routing import (
    ContactOptOutError,
    ContactRoutingPreferences,
    MultiChannelConsentResolver,
    RoutingPolicyService,
    RoutingPolicyViolation,
)
import logging

from app.core.circuit_breaker import CircuitBreakerStore, get_circuit_breaker_store

logger = logging.getLogger(__name__)

class RoutingEngine:
    """Motor de decisão para roteamento de mensagens"""

    def __init__(
        self,
        db: Session,
        org_id: str,
        *,
        circuit_breaker: Optional[CircuitBreakerStore] = None,
        consent_resolver: Optional[MultiChannelConsentResolver] = None,
        policy_service: Optional[RoutingPolicyService] = None,
    ):
        self.db = db
        self.org_id = org_id
        self._circuit_breaker = circuit_breaker or get_circuit_breaker_store()
        self._consent_resolver = consent_resolver or MultiChannelConsentResolver(db, org_id)
        self._policy_service = policy_service or RoutingPolicyService()
    
    def select_provider(
        self,
        country_iso: str,
        category: str,
        template_id: Optional[str] = None,
        *,
        channel: Optional[str] = None,
        contact_address: Optional[str] = None,
        send_time: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Seleciona o provedor baseado nas regras ativas e custos

        Returns:
            Dict com provider_id, fallback_chain, estimated_cost
        """
        # 1. Buscar regras ativas ordenadas por prioridade
        rules = self.db.query(RoutingRule).filter(
            RoutingRule.org_id == self.org_id,
            RoutingRule.is_enabled.is_(True)
        ).order_by(RoutingRule.priority.asc()).all()

        normalized_channel = self._normalize_channel(channel)

        try:
            self._policy_service.validate(
                template_category=category,
                channel=normalized_channel,
                requested_at=send_time or datetime.now(timezone.utc),
            )
        except RoutingPolicyViolation as exc:
            logger.info(
                "Routing policy violation for org %s: %s",
                self.org_id,
                exc.message,
                extra={
                    "event": "routing_policy_violation",
                    "policy_code": exc.code,
                    "channel": normalized_channel,
                    "category": category,
                },
            )
            raise
        preferences: Optional[ContactRoutingPreferences] = None
        if self._consent_resolver and contact_address is not None:
            preferences = self._consent_resolver.resolve(
                channel=normalized_channel,
                channel_address=contact_address,
            )

        denied_by_consent = False
        denied_channel: Optional[str] = normalized_channel

        if (
            preferences
            and preferences.contact_exists
            and normalized_channel
            and contact_address is not None
            and not preferences.is_channel_allowed(normalized_channel, contact_address)
        ):
            raise ContactOptOutError(
                contact_id=preferences.contact_id,
                channel=normalized_channel,
                channel_address=contact_address,
            )

        # 2. Avaliar condições de cada regra
        for rule in rules:
            if not self._evaluate_conditions(
                rule.conditions_json, country_iso, category, template_id
            ):
                continue

            try:
                actions = RoutingRuleActions.model_validate(rule.actions_json or {})
            except ValidationError as exc:
                logger.warning(
                    "Invalid actions_json for rule %s: %s",
                    rule.id,
                    exc,
                )
                continue

            if actions.channel is not None:
                if normalized_channel is None:
                    continue
                if actions.channel != normalized_channel:
                    continue

            candidates: List[Provider] = []
            for provider_id in actions.all_providers():
                provider = self._get_provider(provider_id)
                if not provider:
                    continue

                provider_channel = self._normalize_channel(provider.type)
                if normalized_channel and provider_channel != normalized_channel:
                    continue
                if provider_channel is None:
                    logger.warning(
                        "Provider %s for org %s has no channel type; skipping",
                        provider.id,
                        self.org_id,
                    )
                    continue

                if (
                    preferences
                    and preferences.contact_exists
                    and not preferences.is_channel_allowed(provider_channel, contact_address)
                ):
                    denied_by_consent = True
                    denied_channel = provider_channel
                    continue

                if self._is_provider_blocked(provider):
                    continue

                candidates.append(provider)

            if not candidates:
                continue

            selected_provider = candidates[0]
            estimated_cost = self._get_estimated_cost(selected_provider.id, country_iso, category)
            fallback_ids = [str(provider.id) for provider in candidates[1:]]

            return {
                "provider_id": str(selected_provider.id),
                "fallback_chain": fallback_ids,
                "estimated_cost": estimated_cost,
                "rule_id": str(rule.id),
                "rule_name": rule.name,
            }

        # 3. Fallback: escolher provedor mais barato
        cheapest, cheapest_denied, cheapest_denied_channel = self._find_cheapest_provider(
            country_iso,
            category,
            channel=normalized_channel,
            preferences=preferences,
            contact_address=contact_address,
        )
        if cheapest_denied:
            denied_by_consent = True
            if not denied_channel:
                denied_channel = cheapest_denied_channel
        if cheapest:
            return {
                "provider_id": cheapest["provider_id"],
                "fallback_chain": [],
                "estimated_cost": cheapest["cost"],
                "rule_id": None,
                "rule_name": "auto_cheapest"
            }

        if (
            preferences
            and preferences.contact_exists
            and contact_address is not None
            and (
                denied_by_consent
                or (
                    normalized_channel
                    and not preferences.is_channel_allowed(normalized_channel, contact_address)
                )
                or (
                    not normalized_channel
                    and not preferences.has_allowed_channels_for(contact_address)
                )
            )
        ):
            raise ContactOptOutError(
                contact_id=preferences.contact_id,
                channel=denied_channel,
                channel_address=contact_address,
            )

        logger.warning(f"No provider found for country={country_iso}, category={category}")
        return None
    
    def _evaluate_conditions(
        self,
        conditions: List[Dict[str, Any]],
        country_iso: str,
        category: str,
        template_id: Optional[str]
    ) -> bool:
        """Avalia se as condições da regra são satisfeitas"""
        for condition in conditions:
            cond_type = condition.get("type")
            
            if cond_type == "country":
                if country_iso not in condition.get("values", []):
                    return False
            
            elif cond_type == "category":
                if category not in condition.get("values", []):
                    return False
            
            elif cond_type == "template":
                if template_id and template_id not in condition.get("values", []):
                    return False

        return True

    @staticmethod
    def _normalize_channel(channel: Optional[str]) -> Optional[str]:
        if channel is None:
            return None
        normalized = str(channel).strip().lower()
        return normalized or None

    def _get_provider(self, provider_id: Union[str, UUID]) -> Optional[Provider]:
        try:
            provider_uuid = UUID(str(provider_id))
        except (TypeError, ValueError):
            logger.warning(
                "Invalid provider identifier %s supplied for org %s",
                provider_id,
                self.org_id,
            )
            return None

        return (
            self.db.query(Provider)
            .filter(
                Provider.id == provider_uuid,
                Provider.org_id == self.org_id,
                Provider.status == "active",
            )
            .first()
        )

    def _get_estimated_cost(
        self,
        provider_id: Union[str, UUID],
        country_iso: str,
        category: str,
    ) -> int:
        """Busca custo estimado para o provedor"""
        rate = (
            self.db.query(RateCard)
            .filter(
                RateCard.provider_id == provider_id,
                RateCard.country_iso == country_iso,
                RateCard.category == category,
            )
            .order_by(RateCard.effective_from.desc())
            .first()
        )

        if not rate and country_iso != "GLOBAL":
            rate = (
                self.db.query(RateCard)
                .filter(
                    RateCard.provider_id == provider_id,
                    RateCard.country_iso == "GLOBAL",
                    RateCard.category == category,
                )
                .order_by(RateCard.effective_from.desc())
                .first()
            )

        return rate.unit_cost_minor if rate else 0
    
    def _find_cheapest_provider(
        self,
        country_iso: str,
        category: str,
        *,
        channel: Optional[str] = None,
        preferences: Optional[ContactRoutingPreferences] = None,
        contact_address: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], bool, Optional[str]]:
        """Encontra o provedor mais barato para país/categoria"""
        query = (
            self.db.query(RateCard, Provider)
            .join(Provider, RateCard.provider_id == Provider.id)
            .filter(
                Provider.org_id == self.org_id,
                RateCard.country_iso == country_iso,
                RateCard.category == category,
                Provider.status == "active",
            )
        )

        if channel:
            query = query.filter(func.lower(Provider.type) == channel)

        rates = query.order_by(RateCard.unit_cost_minor.asc()).all()

        denied_by_consent = False
        denied_channel: Optional[str] = None

        for rate, provider in rates:
            provider_channel = self._normalize_channel(provider.type)
            if channel and provider_channel != channel:
                continue

            if self._is_provider_blocked(provider):
                continue

            if (
                preferences
                and preferences.contact_exists
                and provider_channel
                and not preferences.is_channel_allowed(provider_channel, contact_address)
            ):
                denied_by_consent = True
                denied_channel = provider_channel
                continue

            return {
                "provider_id": str(provider.id),
                "cost": rate.unit_cost_minor
            }, denied_by_consent, denied_channel

        return None, denied_by_consent, denied_channel
    
    def calculate_baseline_cost(self, country_iso: str, category: str) -> int:
        """Calcula custo baseline (mais caro) para economia"""
        rate = (
            self.db.query(RateCard)
            .join(Provider, RateCard.provider_id == Provider.id)
            .filter(
                Provider.org_id == self.org_id,
                RateCard.country_iso == country_iso,
                RateCard.category == category,
                Provider.status == "active",
            )
            .order_by(RateCard.unit_cost_minor.desc())
            .first()
        )

        return rate.unit_cost_minor if rate else 0

    def _is_provider_blocked(self, provider: Provider) -> bool:
        if not self._circuit_breaker:
            return False

        state = self._circuit_breaker.get_state(str(provider.id))
        if state.is_blocked():
            logger.info(
                "Skipping provider %s for org %s due to circuit state %s",
                provider.id,
                self.org_id,
                state.state,
            )
            return True

        return False
