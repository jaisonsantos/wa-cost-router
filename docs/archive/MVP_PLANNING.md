# WA Cost Router - Planejamento MVP vs Implementado

## 📊 STATUS ATUAL

### ✅ O QUE JÁ ESTÁ IMPLEMENTADO

#### Backend
- ✅ Sistema de autenticação JWT (login/register)
- ✅ Multi-tenancy (org_id em todas as tabelas)
- ✅ Models básicos: Organization, User, MessageEvent, RateCard, RoutingRule
- ✅ API de Relatórios (`/reports/summary`)
- ✅ API de Eventos (`/events`)
- ✅ API de Regras (`/rules` - CRUD + toggle + simulate básico)
- ✅ API de Rates (`/rates` + import CSV)
- ✅ Webhook WhatsApp básico (`/integrations/wa/webhook`)
- ✅ Conexão WhatsApp (`/integrations/wa/connections`)
- ✅ RoleEnum (Owner, Member) - modelo existe mas não aplicado

#### Frontend
- ✅ Autenticação completa (Login, Register, Logout)
- ✅ AuthContext + JWT storage
- ✅ API Client com interceptors
- ✅ React Query hooks para todas as APIs
- ✅ Dashboard com métricas reais
- ✅ Rules page (listar, toggle, simulate)
- ✅ Reports page (filtros, agregações)
- ✅ Settings page (WA connection, CSV import)
- ✅ Layout com navegação

---

## 🎯 MVP MÍNIMO (End-to-End Funcional)

**Objetivo**: Sistema funcionando com 1 provedor, roteamento básico, e economia visível.

### 1. Roteamento em Produção (CRÍTICO)
**Status**: ❌ NÃO IMPLEMENTADO

**O que falta**:
- [ ] Endpoint `POST /send_message` (proxy/orquestrador)
- [ ] Motor de decisão: aplica regras + escolhe provedor
- [ ] Idempotência (idempotency_key)
- [ ] Tracking de `DeliveryAttempt` (status, latency, error_code)
- [ ] Cálculo de custo real por mensagem (`CostRecord`)
- [ ] Retry básico (3 tentativas com backoff)
- [ ] Fallback simples (se regra define fallback_provider)

**Models necessários**:
```python
# Adicionar em models.py
class MessageJob(Base):
    id = UUID
    org_id = UUID
    idempotency_key = str (unique per org)
    to_number = str
    template_id = str
    variables = JSON
    status = Enum (pending, processing, delivered, failed)
    created_at, updated_at

class DeliveryAttempt(Base):
    id = UUID
    message_job_id = UUID
    provider_id = UUID (FK to Provider)
    attempt_number = int
    status = Enum (success, failed, timeout)
    error_code = str
    latency_ms = int
    timestamp
```

**API**:
```python
# backend/app/api/messages.py (NOVO)
@router.post("/send")
def send_message(
    data: SendMessageRequest,
    db: Session,
    current_user: dict
):
    # 1. Validar idempotency
    # 2. Buscar regras ativas
    # 3. Aplicar condições (país, categoria)
    # 4. Escolher provider
    # 5. Enviar via provider
    # 6. Gravar DeliveryAttempt + CostRecord
    # 7. Retornar status
```

---

### 2. Múltiplos Provedores (Abstração)
**Status**: ⚠️ PARCIAL (só WhatsApp/360dialog)

**O que falta**:
- [ ] Model `Provider` (id, name, type, status, base_url)
- [ ] Abstração `ProviderConnector` (interface comum)
- [ ] Implementar `Gupshup360DialogConnector`
- [ ] Implementar `GupshupConnector` (2º provider MVP)
- [ ] Health check endpoint `GET /providers/:id/health`
- [ ] Página frontend `/providers` (listar, testar, status)

**Models**:
```python
class Provider(Base):
    id = UUID
    name = str  # "360dialog", "Gupshup"
    type = str  # "whatsapp"
    status = Enum (active, inactive, error)
    base_url = str
    
class ProviderCredential(Base):
    id = UUID
    org_id = UUID
    provider_id = UUID
    credentials_encrypted = JSON  # KMS
```

---

### 3. Simulador Real
**Status**: ⚠️ PARCIAL (existe `/rules/simulate` mas é mock)

**O que falta**:
- [ ] Implementar lógica real de simulação:
  - Input: países[], volumes, categoria
  - Output: custo por provider, rota recomendada, economia
- [ ] Comparação side-by-side de providers
- [ ] UI melhor no frontend (tabela comparativa)

---

### 4. Relatórios de Economia Real
**Status**: ⚠️ PARCIAL (existe summary mas saved=0)

**O que falta**:
- [ ] Calcular `baseline_cost` (custo se não tivesse regras)
- [ ] Calcular `optimized_cost` (custo real com regras aplicadas)
- [ ] Salvar em `EconomySnapshot` (diário)
- [ ] Mostrar no Dashboard: savings real, % saved
- [ ] Gráfico de evolução de economia

---

## 📦 MVP COMPLETO (Features Essenciais)

### 5. Fallback & Retry Inteligente
**Status**: ❌ NÃO IMPLEMENTADO

**O que falta**:
- [ ] Fallback chain nas regras (primary → fallback1 → fallback2)
- [ ] Retry exponencial (backoff: 1s, 2s, 4s)
- [ ] Circuit breaker (se provider falha >70% em 5min, corta)
- [ ] Logs detalhados de cada tentativa

---

### 6. Sync Automático de Preços
**Status**: ⚠️ PARCIAL (manual CSV import apenas)

**O que falta**:
- [ ] Cron job para sync de providers (1x/dia)
- [ ] Buscar preços de APIs dos providers
- [ ] Normalizar moeda (tudo em EUR)
- [ ] Versionamento (`PriceTable.version`)
- [ ] Detecção de variação (se >10%, gera alerta)
- [ ] Changelog de preços

---

### 7. Sistema de Alertas
**Status**: ❌ NÃO IMPLEMENTADO

**O que falta**:
- [ ] Model `Alert` (type, severity, message, ack_by, timestamp)
- [ ] Triggers:
  - Provider outage (erro >50% em 5min)
  - Preço mudou >10%
  - Limite de plano atingido (80%, 100%)
- [ ] Notificações: email (via worker)
- [ ] UI: `/alerts` (listar, acknowledge)

---

### 8. RBAC & Convites
**Status**: ⚠️ PARCIAL (RoleEnum existe mas não aplicado)

**O que falta**:
- [ ] Middleware de permissões (Owner pode tudo, Member read-only)
- [ ] Endpoint `POST /orgs/invite` (gera token de convite)
- [ ] Endpoint `POST /orgs/accept_invite` (usuário aceita)
- [ ] UI: `/settings/team` (listar membros, convidar, remover)

---

### 9. API Keys & Webhooks
**Status**: ❌ NÃO IMPLEMENTADO

**O que falta**:
- [ ] Model `ApiKey` (org_id, key_hash, scopes, expires_at)
- [ ] Endpoint `POST /api_keys` (gerar nova key)
- [ ] Autenticação via API key (além de JWT)
- [ ] Model `Webhook` (org_id, url, events[], secret)
- [ ] Dispatcher de webhooks (quando evento acontece)

---

### 10. Drill-down em Relatórios
**Status**: ⚠️ PARCIAL (agregação básica existe)

**O que falta**:
- [ ] Filtros avançados (país, template, provider, período)
- [ ] Drill-down por campanha (campo `campaign_id` em MessageJob)
- [ ] Export CSV melhor (formato Excel-friendly)
- [ ] Gráficos de tendência (custo por dia, savings acumulado)

---

## 🚀 PÓS-MVP (Próxima Iteração)

### 11. Billing com Stripe
- [ ] Planos: Starter (10k msgs), Growth (100k), Pro (ilimitado)
- [ ] Integração Stripe (checkout, webhooks)
- [ ] Soft limit (aviso em 80%) e hard limit (bloqueia em 100%)
- [ ] Overage (cobrança extra por mensagem além do plano)
- [ ] UI: `/billing` (plano atual, upgrade, histórico)

### 12. Auditoria
- [ ] Model `AuditLog` (user_id, action, entity, changes, timestamp)
- [ ] Logar: criar/editar regra, enviar mensagem, mudar config
- [ ] UI: `/audit` (filtros por usuário, ação, período)

### 13. Templates Avançados
- [ ] Sync automático de templates de providers
- [ ] Mapeamento de templates entre providers
- [ ] Teste de template (preview antes de enviar)

### 14. Rate Limiting
- [ ] Respeitar `429` de providers (retry-after)
- [ ] Throttling interno (max msgs/segundo por org)

### 15. SLA & Performance
- [ ] Métricas Prometheus (`/admin/metrics`)
- [ ] p95 de decisão de rota <200ms
- [ ] Dashboard de observabilidade

### 16. Edge Cases
- [ ] Template não sincronizado (fallback para provider que tem)
- [ ] País não suportado (skip provider na decisão)
- [ ] Mudança de preço durante campanha (travar price epoch)

---

## 📝 PRÓXIMOS PASSOS RECOMENDADOS

### Prioridade 1 (MVP Mínimo - Sem isso não funciona)
1. **Implementar `/send_message` endpoint completo** (models + API + motor de decisão)
2. **Adicionar 2º provider (Gupshup)** (abstração + connector)
3. **Simulador real** (com múltiplos providers)
4. **Economia real no Dashboard** (baseline vs optimized)

### Prioridade 2 (MVP Completo - Essencial para produção)
5. **Fallback & retry** (resilience)
6. **Sync automático de preços** (cron job)
7. **Sistema de alertas** (outage, price change)
8. **RBAC completo** (permissões + convites)

### Prioridade 3 (Pós-MVP - Nice to have)
9. **Billing Stripe**
10. **Auditoria**
11. **Templates sync**

---

## 🎨 PÁGINAS FRONTEND FALTANTES

- [ ] `/providers` - Gerenciar provedores (conectar, testar, health)
- [ ] `/simulate` - Simulador standalone (melhor UX que embed em Rules)
- [ ] `/messages` - Listar mensagens enviadas (com drill-down)
- [ ] `/alerts` - Centro de notificações
- [ ] `/settings/team` - Gerenciar usuários e convites
- [ ] `/settings/api-keys` - Gerar e gerenciar API keys
- [ ] `/settings/webhooks` - Configurar webhooks
- [ ] `/billing` - Plano, uso, upgrade

---

## 🔧 REFATORAÇÕES NECESSÁRIAS

1. **Separar concerns**:
   - `backend/app/services/routing_engine.py` (decisão de rota)
   - `backend/app/services/provider_connectors.py` (abstração)
   - `backend/app/services/cost_calculator.py` (cálculo de economia)

2. **Worker jobs** (RQ/Celery):
   - `sync_prices_job` (diário)
   - `send_alerts_job` (a cada 5min)
   - `recompute_economy_job` (diário)

3. **Testes**:
   - Testes unitários do motor de decisão
   - Testes de integração com providers (mocks)

---

## 📊 CRITÉRIOS DE ACEITE MVP MÍNIMO

- [ ] Enviar mensagem via 2 providers (360dialog, Gupshup)
- [ ] Regra aplicada em produção (se país=BR, usa Gupshup)
- [ ] Fallback funcional (se Gupshup falha, tenta 360dialog)
- [ ] Simulador mostra economia real (comparação de custos)
- [ ] Dashboard mostra savings acumulado (vs baseline)
- [ ] Retry automático (3 tentativas)
- [ ] Logs de delivery attempts visíveis no frontend

---

**DECISÃO**: Focar primeiro em **Prioridade 1** (MVP Mínimo) para ter o fluxo end-to-end funcionando. Depois expandir para **Prioridade 2** (produção-ready).
