from typing import Optional, List, Dict, Any, Union, Iterable, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.models import RoutingRule, Provider, RateCard
from app.services.routing import (
    ContactPreferenceResolver,
    ContactOptOutError,
    ContactRoutingPreferences,
)
import logging

logger = logging.getLogger(__name__)

class RoutingEngine:
    """Motor de decisão para roteamento de mensagens"""
    
    def __init__(self, db: Session, org_id: str):
        self.db = db
        self.org_id = org_id
    
    def select_provider(
        self,
        country_iso: str,
        category: str,
        template_id: Optional[str] = None,
        *,
        contact_address: Optional[str] = None,
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

        preferences = None
        if contact_address is not None:
            resolver = ContactPreferenceResolver(self.db, self.org_id)
            preferences = resolver.load(channel_address=contact_address)

        denied_by_consent = False
        denied_channel: Optional[str] = None

        # 2. Avaliar condições de cada regra
        for rule in rules:
            if self._evaluate_conditions(rule.conditions_json, country_iso, category, template_id):
                # Regra aplicável, extrair ação
                primary_candidate = rule.actions_json.get("primary_provider")
                fallback_chain = rule.actions_json.get("fallback_chain", [])

                candidates: List[Provider] = []

                raw_identifiers: List[Any] = []
                if primary_candidate:
                    raw_identifiers.append(primary_candidate)

                if isinstance(fallback_chain, Iterable) and not isinstance(fallback_chain, (str, bytes)):
                    raw_identifiers.extend(list(fallback_chain))
                elif fallback_chain not in (None, ""):
                    logger.warning(
                        "Invalid fallback chain %r for rule %s; ignoring",
                        fallback_chain,
                        rule.id,
                    )

                for raw_identifier in raw_identifiers:
                    provider = self._get_provider(raw_identifier)
                    if not provider:
                        continue

                    if preferences and not preferences.is_channel_allowed(provider.type, contact_address):
                        denied_by_consent = True
                        denied_channel = provider.type
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
            and contact_address is not None
            and (
                denied_by_consent
                or not preferences.has_allowed_channels_for(contact_address)
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

        return rate.unit_cost_minor if rate else 0
    
    def _find_cheapest_provider(
        self,
        country_iso: str,
        category: str,
        *,
        preferences: Optional[ContactRoutingPreferences] = None,
        contact_address: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], bool, Optional[str]]:
        """Encontra o provedor mais barato para país/categoria"""
        rates = (
            self.db.query(RateCard, Provider)
            .join(Provider, RateCard.provider_id == Provider.id)
            .filter(
                Provider.org_id == self.org_id,
                RateCard.country_iso == country_iso,
                RateCard.category == category,
                Provider.status == "active",
            )
            .order_by(RateCard.unit_cost_minor.asc())
            .all()
        )

        denied_by_consent = False
        denied_channel: Optional[str] = None

        for rate, provider in rates:
            if preferences and not preferences.is_channel_allowed(provider.type, contact_address):
                denied_by_consent = True
                denied_channel = provider.type
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
