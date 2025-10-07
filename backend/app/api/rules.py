from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Any
from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.models import RoutingRule

router = APIRouter()

class RuleCreate(BaseModel):
    name: str
    is_enabled: bool = True
    conditions: List[Dict[str, Any]]
    actions: Dict[str, Any]
    priority: int = 100

class RuleResponse(BaseModel):
    id: str
    name: str
    is_enabled: bool
    conditions: List[Dict[str, Any]]
    actions: Dict[str, Any]
    priority: int

@router.get("/", response_model=List[RuleResponse])
def list_rules(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    rules = db.query(RoutingRule).filter(
        RoutingRule.org_id == current_user["org_id"]
    ).order_by(RoutingRule.priority.asc()).all()
    
    return [
        RuleResponse(
            id=str(r.id),
            name=r.name,
            is_enabled=r.is_enabled,
            conditions=r.conditions_json,
            actions=r.actions_json,
            priority=r.priority
        )
        for r in rules
    ]

@router.post("/", response_model=RuleResponse)
def create_rule(
    data: RuleCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    rule = RoutingRule(
        org_id=current_user["org_id"],
        name=data.name,
        is_enabled=data.is_enabled,
        conditions_json=data.conditions,
        actions_json=data.actions,
        priority=data.priority
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    return RuleResponse(
        id=str(rule.id),
        name=rule.name,
        is_enabled=rule.is_enabled,
        conditions=rule.conditions_json,
        actions=rule.actions_json,
        priority=rule.priority
    )

@router.patch("/{rule_id}")
def update_rule(
    rule_id: str,
    data: RuleCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    rule = db.query(RoutingRule).filter(
        RoutingRule.id == rule_id,
        RoutingRule.org_id == current_user["org_id"]
    ).first()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    rule.name = data.name
    rule.is_enabled = data.is_enabled
    rule.conditions_json = data.conditions
    rule.actions_json = data.actions
    rule.priority = data.priority
    
    db.commit()
    return {"status": "updated"}

@router.post("/{rule_id}/toggle")
def toggle_rule(
    rule_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    rule = db.query(RoutingRule).filter(
        RoutingRule.id == rule_id,
        RoutingRule.org_id == current_user["org_id"]
    ).first()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    rule.is_enabled = not rule.is_enabled
    db.commit()
    
    return {"is_enabled": rule.is_enabled}

class SimulateResponse(BaseModel):
    baseline: int
    optimized: int
    saved: int

class SimulateRequest(BaseModel):
    countries: List[str]
    volumes: Dict[str, int]  # country -> volume
    category: str = "marketing"

class ProviderBreakdown(BaseModel):
    provider_id: str
    provider_name: str
    cost_minor: int
    available: bool

class CountryBreakdown(BaseModel):
    country: str
    volume: int
    baseline_cost: int
    optimized_cost: int
    saved: int
    providers: List[ProviderBreakdown]
    recommended_provider: str

class AdvancedSimulateResponse(BaseModel):
    total_baseline: int
    total_optimized: int
    total_saved: int
    breakdown: List[CountryBreakdown]
    recommended_route: Dict[str, str]  # country -> provider_id

@router.post("/simulate", response_model=SimulateResponse)
def simulate(
    data: SimulateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Simulador real de economia
    Calcula custo otimizado vs baseline para múltiplos países
    """
    from app.services.routing_engine import RoutingEngine
    
    engine = RoutingEngine(db, current_user["org_id"])
    
    total_baseline = 0
    total_optimized = 0
    
    for country in data.countries:
        volume = data.volumes.get(country, 0)
        
        # Custo baseline (mais caro)
        baseline_cost = engine.calculate_baseline_cost(country, data.category)
        
        # Custo otimizado (com regras)
        routing = engine.select_provider(country, data.category)
        optimized_cost = routing["estimated_cost"] if routing else baseline_cost
        
        total_baseline += baseline_cost * volume
        total_optimized += optimized_cost * volume
    
    saved = total_baseline - total_optimized
    
    return SimulateResponse(baseline=total_baseline, optimized=total_optimized, saved=saved)

@router.post("/simulate-advanced", response_model=AdvancedSimulateResponse)
def simulate_advanced(
    data: SimulateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Simulador avançado com breakdown detalhado por país e provedor
    """
    from app.services.routing_engine import RoutingEngine
    from app.models.models import RateCard, Provider
    
    engine = RoutingEngine(db, current_user["org_id"])
    
    total_baseline = 0
    total_optimized = 0
    breakdown = []
    recommended_route = {}
    
    # Buscar todos os provedores ativos
    providers = db.query(Provider).filter(
        Provider.org_id == current_user["org_id"],
        Provider.status == "active"
    ).all()
    
    for country in data.countries:
        volume = data.volumes.get(country, 0)
        
        # Calcular custo baseline (mais caro)
        baseline_cost = engine.calculate_baseline_cost(country, data.category)
        
        # Calcular custo para cada provedor
        provider_costs = []
        cheapest_provider = None
        cheapest_cost = float('inf')
        
        for provider in providers:
            # Buscar tarifa do provedor
            rate = (
                db.query(RateCard)
                .filter(
                    RateCard.provider_id == provider.id,
                    RateCard.country_iso == country,
                    RateCard.category == data.category,
                )
                .order_by(RateCard.effective_from.desc())
                .first()
            )
            
            if rate:
                cost = rate.unit_cost_minor
                provider_costs.append(ProviderBreakdown(
                    provider_id=str(provider.id),
                    provider_name=provider.name,
                    cost_minor=cost,
                    available=True
                ))
                
                if cost < cheapest_cost:
                    cheapest_cost = cost
                    cheapest_provider = str(provider.id)
            else:
                provider_costs.append(ProviderBreakdown(
                    provider_id=str(provider.id),
                    provider_name=provider.name,
                    cost_minor=0,
                    available=False
                ))
        
        # Custo otimizado (com regras ou mais barato)
        routing = engine.select_provider(country, data.category)
        if routing:
            optimized_cost = routing["estimated_cost"]
            recommended_provider = routing["provider_id"]
        elif cheapest_provider:
            optimized_cost = cheapest_cost
            recommended_provider = cheapest_provider
        else:
            optimized_cost = baseline_cost
            recommended_provider = ""
        
        country_baseline = baseline_cost * volume
        country_optimized = optimized_cost * volume
        country_saved = max(0, country_baseline - country_optimized)
        
        total_baseline += country_baseline
        total_optimized += country_optimized
        
        breakdown.append(CountryBreakdown(
            country=country,
            volume=volume,
            baseline_cost=country_baseline,
            optimized_cost=country_optimized,
            saved=country_saved,
            providers=provider_costs,
            recommended_provider=recommended_provider
        ))
        
        if recommended_provider:
            recommended_route[country] = recommended_provider
    
    total_saved = max(0, total_baseline - total_optimized)
    
    return AdvancedSimulateResponse(
        total_baseline=total_baseline,
        total_optimized=total_optimized,
        total_saved=total_saved,
        breakdown=breakdown,
        recommended_route=recommended_route
    )
