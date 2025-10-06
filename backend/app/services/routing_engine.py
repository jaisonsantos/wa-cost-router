from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.models.models import RoutingRule, Provider, RateCard
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
        template_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Seleciona o provedor baseado nas regras ativas e custos
        
        Returns:
            Dict com provider_id, fallback_chain, estimated_cost
        """
        # 1. Buscar regras ativas ordenadas por prioridade
        rules = self.db.query(RoutingRule).filter(
            RoutingRule.org_id == self.org_id,
            RoutingRule.is_enabled == True
        ).order_by(RoutingRule.priority.asc()).all()
        
        # 2. Avaliar condições de cada regra
        for rule in rules:
            if self._evaluate_conditions(rule.conditions_json, country_iso, category, template_id):
                # Regra aplicável, extrair ação
                provider_id = rule.actions_json.get("primary_provider")
                fallback_chain = rule.actions_json.get("fallback_chain", [])

                if provider_id:
                    provider = self._get_provider(provider_id)
                    if not provider:
                        logger.warning(
                            "Routing rule %s references provider %s not available for org %s",
                            rule.id,
                            provider_id,
                            self.org_id,
                        )
                        continue

                    estimated_cost = self._get_estimated_cost(provider, country_iso, category)
                    valid_fallbacks = [
                        fb
                        for fb in fallback_chain
                        if self._get_provider(fb) is not None
                    ]

                    return {
                        "provider_id": str(provider.id),
                        "fallback_chain": valid_fallbacks,
                        "estimated_cost": estimated_cost,
                        "rule_id": str(rule.id),
                        "rule_name": rule.name,
                    }
        
        # 3. Fallback: escolher provedor mais barato
        cheapest = self._find_cheapest_provider(country_iso, category)
        if cheapest:
            return {
                "provider_id": cheapest["provider_id"],
                "fallback_chain": [],
                "estimated_cost": cheapest["cost"],
                "rule_id": None,
                "rule_name": "auto_cheapest"
            }
        
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
    
    def _get_provider(self, provider_id: str) -> Optional[Provider]:
        return (
            self.db.query(Provider)
            .filter(
                Provider.id == provider_id,
                Provider.org_id == self.org_id,
                Provider.status == "active",
            )
            .first()
        )

    def _get_estimated_cost(self, provider: Provider, country_iso: str, category: str) -> int:
        """Busca custo estimado para o provedor"""
        rate = (
            self.db.query(RateCard)
            .filter(
                RateCard.source == provider.name,
                RateCard.country_iso == country_iso,
                RateCard.category == category,
            )
            .order_by(RateCard.effective_from.desc())
            .first()
        )

        return rate.unit_cost_minor if rate else 0
    
    def _find_cheapest_provider(self, country_iso: str, category: str) -> Optional[Dict[str, Any]]:
        """Encontra o provedor mais barato para país/categoria"""
        rates = (
            self.db.query(RateCard, Provider)
            .join(Provider, RateCard.source == Provider.name)
            .filter(
                Provider.org_id == self.org_id,
                RateCard.country_iso == country_iso,
                RateCard.category == category,
                Provider.status == "active",
            )
            .order_by(RateCard.unit_cost_minor.asc())
            .first()
        )
        
        if rates:
            rate, provider = rates
            return {
                "provider_id": str(provider.id),
                "cost": rate.unit_cost_minor
            }
        
        return None
    
    def calculate_baseline_cost(self, country_iso: str, category: str) -> int:
        """Calcula custo baseline (mais caro) para economia"""
        rate = (
            self.db.query(RateCard)
            .join(Provider, RateCard.source == Provider.name)
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
