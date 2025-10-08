[Docs](./README.md) › AGENTE
# AGENTE.md

## 1. Resumo Executivo

- **Status do MVP**: endurecido para piloto interno, mas ainda não atinge 100% das metas definidas para o piloto externo.
  - APIs de providers e motor de roteamento agora respeitam `org_id` em todas as consultas.
  - Credenciais de provedores passam a ser criptografadas em repouso (Fernet) e a migration 002 cobre dados existentes.
  - Endpoints de mensagens alinharam contratos com o frontend (`is_configured`, `provider_name`, custos acumulados).
  - `GET /rates` agora exige autenticação, eliminando vazamento público.
- **Pendências críticas para 100% das metas**:
  - Mapeamento multi-tenant do webhook WhatsApp e sanitização de payloads/PII continuam bloqueando o piloto externo.
  - O endpoint `/admin/metrics` segue sem proteção; circuito de provedores e rate limiting multicanal ainda não foram validados.
  - Seeds ainda dependem de `create_all`; é necessário concluir a migração para `alembic upgrade` + `seed` em sequência.
- **Matriz de rastreabilidade**: consulte [`USE_CASE_TRACEABILITY`](./USE_CASE_TRACEABILITY.md) para acompanhar status dos casos de uso UC-01 a UC-04 e seus vínculos com backlog e roadmap.

### Estado em 2025-10-08
- O MVP continua bloqueado para o piloto externo porque o webhook WhatsApp ainda não está multi-tenant, mantendo o item crítico [`20251006-webhook-multi-tenant`](../backlog/20251006-webhook-multi-tenant.md) aberto.
- As salvaguardas de conformidade seguem pendentes: sanitização de payloads e logs ([`20251006-sanitizacao-pii`](../backlog/20251006-sanitizacao-pii.md)) e proteção do endpoint de métricas administrativas ([`20251006-proteger-admin-metrics`](../backlog/20251006-proteger-admin-metrics.md)).
- A resiliência multicanal não está validada; o fallback automático depende do circuito de provedores [`20251006-circuit-breaker`](../backlog/20251006-circuit-breaker.md) e o frontend ainda não expõe indicadores multicanal alinhados ao backlog [`20250210-analytics-dashboard-sync`](../backlog/20250210-analytics-dashboard-sync.md).

### Próximos passos herdados

| Fonte | Referência | Como prosseguir |
| --- | --- | --- |
| Plano de implementação | [`NEXT_IMPLEMENTATION_PLAN.md`](./NEXT_IMPLEMENTATION_PLAN.md) | Executar as tarefas "Next Up" priorizando hardening multi-tenant e ajustes de contratos.
| Roadmap revisado | [`README.md`](./README.md) | Sincronizar entregas com o roadmap vigente e reavaliar riscos antes de abrir o piloto externo.

## 2. Mapa do Repositório

| Caminho | Papel | Observações |
| --- | --- | --- |
| `backend/app/main.py` | Inicialização FastAPI, CORS, routers | CORS restrito a localhost; precisa parametrização.

 |
| `backend/app/api/` | Endpoints REST (auth, mensagens, regras, relatórios, provedores, rates, integrações) | Providers/rates agora filtram `org_id`; webhook ainda precisa de mapeamento multi-tenant. |
| `backend/app/core/` | Config, DB, segurança | Secrets default; módulo `security` expõe Fernet para tokens e credenciais.

 |
| `backend/app/models/models.py` | ORM | `ProviderCredential.credentials_encrypted` convertido para texto criptografado; unique de idempotência consolidada.

 |
| `backend/app/services/` | `RoutingEngine`, conectores HTTPX | RoutingEngine impõe `org_id`; respostas completas dos provedores são persistidas.

 |
| `backend/scripts/` | Seeds | `seed.py` assume migrations aplicadas e popula dados demo de forma idempotente; `seed_providers` aceita `--org-id` (ou executa para todas). |
| `backend/alembic/` | Config/migrations | Revisões `000`–`005` cobrem schema base, FK de `message_job` e vínculo `rate_card → provider`. |
| `backend/worker.py` | Worker RQ | Pronto para background jobs.

 |
| `src/` | Front-end Vite/React | Hooks em `src/hooks/useApi.ts`; telas em `src/pages/`; contratos divergentes. |
| `docker-compose.yml` | Orquestração local | Executa migration antes do seed (ordem incorreta).

 |
| Docs raiz | `README`, `docs/` | README reescrito com demo; `docs/` centraliza arquitetura, operações e segurança. |

### Backend — pendências críticas
- [ ] Webhook WhatsApp multi-tenant para roteamento inbound/outbound seguro ([`20251006-webhook-multi-tenant`](../backlog/20251006-webhook-multi-tenant.md)).
- [ ] Sanitização de PII em payloads e respostas ([`20251006-sanitizacao-pii`](../backlog/20251006-sanitizacao-pii.md)).
- [ ] Circuit breaker e fallback multicanal monitorado ([`20251006-circuit-breaker`](../backlog/20251006-circuit-breaker.md)).
- [ ] Proteção do endpoint `/admin/metrics` e hardening operacional ([`20251006-proteger-admin-metrics`](../backlog/20251006-proteger-admin-metrics.md)).

### Frontend — pendências críticas
- [ ] Ajustar contratos API ↔ SPA antes do piloto externo ([`20251006-contratos-api-fe`](../backlog/20251006-contratos-api-fe.md)).
- [ ] Expor indicadores e fallback multicanal alinhados às novas fontes de dados ([`20250210-analytics-dashboard-sync`](../backlog/20250210-analytics-dashboard-sync.md)).
- [ ] Preparar telas de branding/white-label e RBAC por tenant (depende de [`20250210-worker-offload`](../backlog/20250210-worker-offload.md) e épico E4 para governança).

## 3. Inventário de Endpoints

### Endpoints prototipados (MVP)

| Endpoint | Cobertura atual | Lacunas conhecidas |
| --- | --- | --- |
| `POST /messages/send` | Autenticado, grava `MessageJob`, `DeliveryAttempt` e `CostRecord` com `price_table_version="v1"`. | Falta validação E.164 e sanitização dos campos `variables`/`provider_response` (PII exposta). |
| `GET /messages/jobs` | Lista jobs com `template_category`, `total_cost_minor` e filtros por status. | Retorno limitado a 100 itens; contratos ainda precisam de revisão com a SPA. |
| `GET /messages/jobs/{job_id}` | Devolve tentativas com `provider_name`, `attempt.id` e custos agregados. | Erros retornam texto bruto do provedor. |
| `POST /rules` / `PATCH /rules/{id}` / `POST /rules/{id}/toggle` | CRUD funcional; toggle retorna `{is_enabled}`. | Atualização exige payload completo; falta auditoria de mudanças. |
| `POST /rules/simulate-advanced` | Calcula estimativas `total_baseline/total_optimized`. | Contrato diverge do frontend (`baseline_cost`, `optimized_cost`, `total_savings`, `provider_comparison`). |
| `GET /reports/dashboard-metrics` | Disponibiliza métricas agregadas (`total_messages`, `saved_minor`, etc.). | Requer `MessageEvent` externo; sem baseline real sem ingestão automática. |
| `GET /reports/provider-metrics` | Exibe performance por provedor. | Falta particionamento por org quando novos providers forem inseridos. |
| `GET /providers` / `POST /providers/credentials` | Lista providers e salva credenciais criptografadas (Fernet). | Health-checks ainda dependem de credenciais hardcoded para demo. |
| `GET /rates` | Autenticação obrigatória e ordenação por `effective_from`. | Tarifas ainda globais, sem `org_id`. |
| `POST /integrations/wa/connections` | Persiste tokens WA criptografados. | Sem rotação/expiração automática. |

### Endpoints pendentes ou incompletos

| Endpoint/fluxo | Status | Impacto |
| --- | --- | --- |
| `POST /integrations/wa/webhook` | `org_id` hardcoded; sem roteamento multi-tenant. | Bloqueia o piloto externo (item [`20251006-webhook-multi-tenant`](../backlog/20251006-webhook-multi-tenant.md)). |
| `/admin/metrics` | Público, sem autenticação ou RBAC. | Exposição de métricas sensíveis até que [`20251006-proteger-admin-metrics`](../backlog/20251006-proteger-admin-metrics.md) seja concluído. |
| Rate limiting por tenant | Não implementado. | Risco de abuso e instabilidade enquanto [`20251006-circuit-breaker`](../backlog/20251006-circuit-breaker.md) estiver aberto. |
| Sanitização de payloads/logs | Não implementada. | Requisito de conformidade pendente ([`20251006-sanitizacao-pii`](../backlog/20251006-sanitizacao-pii.md)). |

### Páginas prototipadas (SPA)

| Página | Status atual | Observações |
| --- | --- | --- |
| Login / Register | Fluxos básicos prontos com consumo das APIs de autenticação. | Falta hardening de UX (tratamento de erro, políticas de senha). |
| Dashboard | Exibe cards de métricas conforme `GET /reports/dashboard-metrics`. | Indicadores multicanal ainda mockados. |
| Messages | Lista jobs e detalhes usando `GET /messages/jobs` e `GET /messages/jobs/{job_id}`. | Falta alinhamento de contrato para campos adicionais e filtros avançados. |
| Providers | CRUD completo para cadastro e health-check. | Tela ainda assume um único tenant. |
| Rules | Editor de regras com fallback chain. | Não registra histórico de alterações nem simulações persistidas. |
| Reports | Consome métricas agregadas dos endpoints de relatórios. | Gráficos não refletem dados multicanal reais. |
| Settings | Ajustes gerais e tokens. | RBAC e branding white-label não estão expostos. |
| NotFound / Index | Fluxos básicos de roteamento. | Sem customização por org. |

### Páginas e fluxos pendentes

| Página/fluxo | Status | Dependências |
| --- | --- | --- |
| Branding/white-label | Não iniciado. | Depende do épico de governança e do backlog [`20250210-worker-offload`](../backlog/20250210-worker-offload.md). |
| RBAC por tenant / gestão de usuários | Não iniciado. | Bloqueado pela definição de papéis no roadmap do ciclo e pelo hardening de autenticação. |
| Indicadores multicanal em tempo real | Parcial (mock). | Necessita concluir [`20250210-analytics-dashboard-sync`](../backlog/20250210-analytics-dashboard-sync.md) e instrumentar circuit breaker. |
| Monitoramento de custos avançados | Não iniciado. | Depende da ingestão automática de baseline e trilhas de auditoria de custos. |



## 4. Multi-Tenancy

| Item | Status | Risco |
| --- | --- | --- |
| Providers API | ✅ Filtro `org_id` aplicado em credenciais/health | Reduzido. Monitorar novos endpoints.
| RoutingEngine | ✅ Provider restrito ao tenant em regra, fallback filtrado | Fallback automático permanece dependente de `RateCard` global. |
| Rates | ✅ Auth obrigatória; dados ainda globais | Considerar `org_id` em rate cards customizados. |
| Webhook WA | `org_id` placeholder | Eventos não associados à org correta.

 |
| Seeds | `seed_providers` respeita `org_id` informado ou replica para todas | Seed não cria org automaticamente. |

## 5. Idempotência

- Constraint `(org_id,idempotency_key)` em `MessageJob` consolidada (removida duplicidade de `__table_args__`).


- `POST /messages/send` consulta job existente e retorna resposta idempotente.



## 6. Auditoria de Custos

- `CostRecord` guarda `price_table_version`, país, categoria e `price_eur`.


- `send_message` registra estimativa com versão fixa “v1”.


- Relatórios usam `MessageEvent.unit_cost_minor` vs `baseline_cost_minor`; sem ingest automático não há baseline real.




## 7. Segurança

| Aspecto | Situação |
| --- | --- |
| Criptografia | Tokens WA e credenciais de provedores criptografados com Fernet (migration 002).

 |
| Dados sensíveis | `variables` e `provider_response` armazenam payload possivelmente com PII.

 |
| Validação entradas | Sem E.164 (apenas mapa de prefixos).

 |
| Rate limiting | Inexistente. |
| Admin metrics | `/admin/metrics` público, sem auth.

 |
| Secrets | Valores padrão `change-this`/`please-change-me` no config.

 |
| CORS/HTTPS | Apenas origens localhost; precisa ajustes para produção.

 |

## 8. Resiliência

- Implementado: retries (3 tentativas, exponential backoff), fallback chain, logging de erros.


- Ausente: circuit breaker, métricas estruturadas, integração do worker RQ, limites de latência configuráveis. Conectores dependem de HTTPX com timeout fixo (30s).



## 9. Migrations

- Revisão 001 ajusta colunas/constraints; pressupõe tabelas existentes.


- Em base nova: `alembic upgrade head` falha (tabelas inexistentes) antes do `seed`. Necessário criar migration “base schema” e reorganizar `docker-compose` (seed após migrations).


- Verificações sugeridas: `alembic history`, `alembic current`, `\d message_job`, `\d provider`.

## 10. Plano Técnico (Fases)

| Fase | Objetivos | Tarefas (DoD / riscos / estimativa) |
| --- | --- | --- |
| **Fase 1 – Hardening** | Multi-tenancy & segurança | (a) Filtrar `org_id` em providers/RoutingEngine + testes multi-org (3d). (b) Criptografar `ProviderCredential` (migração + decrypt nos conectores) (4d). (c) Ajustar contratos API/UI (2d). |
| **Fase 2 – Observabilidade & Resiliência** | Estabilizar operação | (a) Circuit breaker + métricas Prometheus (4d). (b) Validação E.164 e sanitização de logs (2d). (c) Rate limiting por org (Redis) (3d). |
| **Fase 3 – Monetização & Governança** | Escalar produto | (a) Stripe Billing/Tax (7d). (b) RBAC + API keys (4d). (c) Webhooks externos e auditoria (7d). |

## 11. Suite de Testes Manuais (15–30 min)

1. **Setup**  
   ```bash
   docker-compose down -v
   docker-compose up -d db redis
   sleep 10
   docker-compose run --rm api alembic upgrade head      # após corrigir migrations
   docker-compose run --rm api python scripts/seed.py
   docker-compose up -d
   ```
2. **Registrar & logar**  
   ```bash
   curl -X POST http://localhost:8000/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email":"pilot@example.com","password":"Passw0rd!","org_name":"Design Partner"}'
   ```
3. **Criar provider + credenciais** (usar UUID retornado)  
   ```bash
   curl -X POST http://localhost:8000/providers \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"name":"360dialog","type":"whatsapp","base_url":"https://waba.360dialog.io/v1"}'
   curl -X POST http://localhost:8000/providers/credentials \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"provider_id":"UUID","credentials":{"access_token":"invalid-demo"}}'
   ```
4. **Criar regra**  
   ```bash
   curl -X POST http://localhost:8000/rules \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"name":"BR->360","is_enabled":true,"conditions":[{"type":"country","values":["BR"]}],
          "actions":{"primary_provider":"UUID","fallback_chain":[]},
          "priority":10}'
   ```
5. **Simular avançado**  
   ```bash
   curl -X POST http://localhost:8000/rules/simulate-advanced \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"countries":["BR"],"volumes":{"BR":1000},"category":"marketing"}'
   ```
6. **Enviar mensagem (checar idempotência)**  
   ```bash
   curl -X POST http://localhost:8000/messages/send \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"idempotency_key":"job-001","to_number":"+5511999999999","template_id":"welcome","template_category":"marketing","variables":{}}'
   curl -X POST http://localhost:8000/messages/send \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"idempotency_key":"job-001","to_number":"+5511999999999","template_id":"welcome","template_category":"marketing","variables":{}}'
   ```
7. **Consultar jobs e métricas**  
   ```bash
   curl http://localhost:8000/messages/jobs -H "Authorization: Bearer $TOKEN"
   curl http://localhost:8000/messages/jobs/$JOB_ID -H "Authorization: Bearer $TOKEN"
   curl http://localhost:8000/reports/dashboard-metrics -H "Authorization: Bearer $TOKEN"
   curl http://localhost:8000/reports/provider-metrics -H "Authorization: Bearer $TOKEN"
   ```

## 12. Plano de Deploy

1. **Secrets obrigatórios**: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `APP_SECRET_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `WA_VERIFY_TOKEN`, `SMTP_*`.  
2. **Infra**: Postgres gerenciado com backups PITR; Redis gerenciado; bucket para dumps.  
3. **Pipeline**:
   - `docker-compose -f docker-compose.yml pull`
   - `docker-compose run --rm api alembic upgrade head`
   - `docker-compose up -d api worker`
4. **Reverse proxy TLS** (Nginx/Caddy):
   - Certificados Let’s Encrypt + HSTS.
   - Rate limiting (100 req/min/org) via nginx/Redis.
   - Redirect HTTP→HTTPS.
5. **Observabilidade**:
   - Proteger `/admin/metrics` com auth e coletar via Prometheus.
   - Logs estruturados enviados para ELK/CloudWatch.
   - Alarmes: latência >3s, taxa de sucesso <95%, falhas de migration.
6. **Checklist (pendências)**:
   - [ ] Migrations reconciliadas em todos os ambientes conforme [`20251006-migration-base`](../backlog/20251006-migration-base.md).
   - [ ] Secrets rotacionados e validados segundo [`20251006-enforce-secret-strength`](../backlog/20251006-enforce-secret-strength.md).
   - [ ] TLS e proteção do endpoint de métricas configurados (ver [`20251006-proteger-admin-metrics`](../backlog/20251006-proteger-admin-metrics.md)).
   - [ ] Sanitização de payloads/PII aplicada antes do rollout externo ([`20251006-sanitizacao-pii`](../backlog/20251006-sanitizacao-pii.md)).

## 13. Riscos & Mitigações

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| Credenciais em texto claro | Alta | Introduzir criptografia Fernet + rotação. |
| Cross-tenant via provider UUID | Alta | Filtro `org_id` obrigatório em queries e rules. |
| Migration quebra ambiente novo | Alta | Criar migration base e ajustar ordem do compose. |
| Dashboard quebrado por contratos | Média | Ajustar API/UI + testes de contrato (pacto). |
| Payload PII em logs/DB | Média | Mascarar `variables` e `provider_response`. |
| Webhook sem org mapping | Alta | Tabela `phone_id -> org_id` e validação. |
| Métricas expostas publicamente | Média | Auth no `/admin/metrics` e rede interna. |
| Ausência de rate limit | Média | Implementar limitador Redis no FastAPI. |
| Circuit breaker ausente | Média | Incluir contadores de falha e fallback automático. |
| Secrets default | Média | Enforce `.env` e validação no boot. |

## 14. Novo README.md

```markdown
# WA Cost Router

> Roteamento inteligente de mensagens WhatsApp com economia de custos e métricas em tempo real.

[![Docker](https://img.shields.io/badge/Docker-ready-blue)](#quick-start) [![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Quick Start

```bash
git clone <repo>
cd wa-cost-router
cp backend/.env.example backend/.env  # preencha secrets
docker-compose up -d --build
```

- API: http://localhost:8000
- Frontend: http://localhost:8080

## Endpoints Essenciais

| Método | Rota | Descrição |
| --- | --- | --- |
| POST | `/messages/send` | Envio com idempotência e fallback |
| GET | `/messages/jobs` | Histórico de jobs da organização |
| GET | `/reports/dashboard-metrics` | Métricas de custo e sucesso |
| POST | `/rules/simulate-advanced` | Simulador de economia |
| POST | `/providers/credentials` | Configuração de provedores |

Mais detalhes em [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md).

## Demo rápida

```bash
# Simulação
curl -X POST http://localhost:8000/rules/simulate-advanced \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"countries":["BR"],"volumes":{"BR":1000},"category":"marketing"}'

# Envio idempotente
curl -X POST http://localhost:8000/messages/send \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"idempotency_key":"demo-1","to_number":"+5511999999999","template_id":"welcome","template_category":"marketing","variables":{}}'

# Consulta de job
curl http://localhost:8000/messages/jobs/$JOB_ID \
  -H "Authorization: Bearer $TOKEN"
```

## Documentação

- [Arquitetura](docs/ARCHITECTURE.md)
- [Modelagem de Dados](docs/DATA_MODEL.md)
- [Operações](docs/OPERATIONS.md)
- [Segurança](docs/SECURITY.md)
- [Roadmap](docs/ROADMAP.md)

## Licença

MIT.
```

## 15. Documentos `docs/`

### docs/ARCHITECTURE.md
```markdown
# Arquitetura

```
React SPA --> FastAPI --> PostgreSQL
              |            ^
              v            |
          RoutingEngine    |
              |            |
        ProviderConnector (HTTPX) --> Provedores externos
```

- **Frontend** (`src/`): React + React Query, AuthContext.
- **API** (`backend/app/`): módulos `api`, `core`, `models`, `services`.
- **Mensageria**: `RoutingEngine` aplica regras (`routing_rule`) e consulta `RateCard`.
- **Persistência**: `MessageJob`, `DeliveryAttempt`, `CostRecord`, `MessageEvent`.
- **Observabilidade**: `/admin/metrics` (Prometheus), logging padrão.
- **Integrações**: `integrations.py` recebe Webhooks WhatsApp (mapear `org_id`).
- **Trabalhos assíncronos**: `worker.py` (Redis + RQ) pronto para offloading futuro.

Fluxo de envio:
1. `POST /messages/send` cria `MessageJob`.
2. `RoutingEngine.select_provider()` -> `ProviderCredential` -> `ProviderConnector.send_message()`.
3. `DeliveryAttempt` + `CostRecord`.
4. Job atualizado (delivered/delivered_with_fallback/failed_final).
```

### docs/API_REFERENCE.md
```markdown
# API Reference (Resumo)

Todas as rotas abaixo exigem `Authorization: Bearer <token>` salvo indicação contrária.

## Autenticação
- `POST /auth/register` `{ email, password, org_name }` → `{ access_token }`
- `POST /auth/login` `{ email, password }` → `{ access_token }`

## Mensagens
- `POST /messages/send` → `SendMessageResponse`
- `GET /messages/jobs?status=...` → `{ "jobs": [...] }`
- `GET /messages/jobs/{job_id}` → detalhes + tentativas

## Regras
- `GET /rules`
- `POST /rules`
- `PATCH /rules/{id}` (payload completo)
- `POST /rules/{id}/toggle`
- `POST /rules/simulate-advanced`

## Relatórios
- `GET /reports/dashboard-metrics?days=7`
- `GET /reports/provider-metrics?days=7`
- `GET /reports/summary?from=YYYY-MM-DD&to=YYYY-MM-DD`

## Provedores
- `GET /providers`
- `POST /providers`
- `POST /providers/credentials`
- `POST /providers/{id}/health`
- `DELETE /providers/{id}/credentials`

## Tarifas
- `GET /rates` (precisa de auth futura)
- `POST /rates/import_csv`

## Integrações
- `POST /integrations/wa/connections`
- `GET /integrations/wa/webhook`
- `POST /integrations/wa/webhook` (TODO: mapear org)

## Admin
- `GET /admin/health`
- `GET /admin/metrics` (proteger)
```

### docs/DATA_MODEL.md
```markdown
# Modelagem de Dados

## Principais Entidades

| Tabela | Campos-chave | Notas |
| --- | --- | --- |
| `organization` | `id`, `name` | Tenant. |
| `user`, `organization_user` | `email`, `role`, `org_id` | `role` enum (`owner`, `member`). |
| `provider` | `org_id`, `name`, `type`, `status` | Unique `(org_id,name)`. |
| `provider_credential` | `org_id`, `provider_id`, `credentials_encrypted` | Deve receber criptografia real. |
| `routing_rule` | `org_id`, `conditions_json`, `actions_json`, `priority`, `is_enabled` | JSON com condicionais e provedores. |
| `message_job` | `org_id`, `idempotency_key`, `status` | Unique `(org_id,idempotency_key)`. |
| `delivery_attempt` | `message_job_id`, `provider_id`, `attempt_number`, `status`, `provider_response` | Armazena resposta crua. |
| `cost_record` | `message_job_id`, `provider_id`, `price_eur`, `price_table_version` | Auditoria de custo. |
| `message_event` | `org_id`, `message_job_id`, `provider_event_id`, `unit_cost_minor`, `baseline_cost_minor` | Base para relatórios (referência opcional para `message_job`). |
| `rate_card` | `provider_id`, `country_iso`, `category`, `unit_cost_minor` | Tarifa vinculada a um provedor ativo. |
| `wa_connection` | `org_id`, `business_id`, `phone_id`, `access_token_enc` | Token WhatsApp criptografado. |

## ERD (ASCII)

```
organization ──< organization_user >── user
     │                             
     ├──< provider ──< provider_credential
     │         │
     │         └──< message_job ──< delivery_attempt
     │                           └──< cost_record
     │
     ├──< routing_rule
     ├──< message_event
     └──< wa_connection

rate_card ──> provider
```

## Índices & Constraints

- `message_job`: unique `(org_id,idempotency_key)`, index em `created_at`.
- `provider`: unique `(org_id,name)`, índice `org_id`.
- `delivery_attempt`: PK UUID, sem índices adicionais – considerar índice em `(message_job_id, attempt_number)`.
- `message_event`: índices em `org_id`, `provider_event_id`, `timestamp_provider`; FK opcional `message_job_id`.

## Observações

- Schema consolidado via migrations Alembic (`000_base_schema` → `005_link_rate_cards_to_providers`).
- `rate_card` agora referencia `provider` diretamente; backlog P3 discute escopo por tenant.
- `provider_response` e `variables` precisam de sanitização/anonimização.
```

### docs/SECURITY.md
```markdown
# Segurança & Hardening

## Estado Atual

- **Autenticação**: JWT HS256 com expiração 7 dias, `org_id` no payload.


- **Criptografia**: tokens WhatsApp via Fernet (`APP_SECRET_KEY`). Provedores armazenados em JSON puro.
- **Multi-tenancy**: filtros `org_id` em jobs, regras e relatórios; lacunas em providers, RoutingEngine e webhook.
- **Logs**: sem mascaramento; provider responses persistidos.
- **Endpoints sensíveis**: `/admin/metrics` público; `GET /rates` sem auth.

## Ações Recomendadas (Prioridade Alta)

1. **Criptografia de `ProviderCredential`**
   - Funções `encrypt_credentials`/`decrypt_credentials` derivando chave de `APP_SECRET_KEY`.
   - Migração para converter JSON existente em blob criptografado.
2. **Filtros multi-tenant obrigatórios**
   - Providers (`set_provider_credentials`, `health`) e `RoutingEngine` com `org_id`.
   - Mapear `phone_id -> org_id` no webhook.
3. **Validação de entradas**
   - Biblioteca `phonenumbers` para E.164.
   - Sanitização de `variables` e `provider_response` (hash ou truncar).
4. **Proteção de métricas/admin**
   - Autenticação (basic auth ou token) em `/admin/metrics`.
   - Mover endpoints admin para rede interna.
5. **Rate limiting**
   - Middleware com Redis (ex. SlowAPI) limitando requests por org e por rota crítica.
6. **Secrets & Config**
   - Enforce override de `JWT_SECRET`/`APP_SECRET_KEY` em produção.
   - TLS obrigatório; CORS configurável via env.

## Ações Futuras

- RBAC (owner/member) com autorização por rota.
- Audit log centralizado (credenciais, regras, envios).
- Monitoramento de acesso (alerta para falhas de login).
- Revisão LGPD/GDPR: retenção mínima de dados e consentimento.

## Testes de Segurança Recomendados

- **Multi-tenant**: registrar duas orgs, tentar acessar provider/rule de outra via UUID.
- **Idempotência**: enviar mesma chave duas vezes (ver job único).
- **Injection**: payload malicioso em `variables` (validar escapes).
- **Rate limit**: stress `POST /messages/send` após implementar limitação.
```

### docs/OPERATIONS.md
```markdown
# Operações & Runbooks

## 1. Migrations

```bash
docker-compose run --rm api alembic history
docker-compose run --rm api alembic upgrade head
```

- Em banco vazio: rodar migration base (após criação) antes de iniciar API.
- Verificar constraints: `docker-compose exec db psql -U postgres -d wa_cost_router -c "\d message_job"`.

## 2. Seed

- `python scripts/seed.py` cria org demo + dados sintéticos (usa `metadata.create_all` – substituir por migrations futuras).
- `python scripts/seed_providers.py --org-id <uuid>` popula uma organização específica; sem argumento replica para todas.

## 3. Saúde

- `GET /admin/health` (após proteger) para readiness.
- `POST /providers/{id}/health` para conectividade com provedores.

## 4. Logs & Monitoramento

- Uvicorn logs stdout; configurar agregador (ELK/CloudWatch).
- Prometheus: `/admin/metrics` (contagem `app_requests_total`).

## 5. Métricas

- Key KPIs:
  - Taxa de sucesso `success_rate` (`/reports/dashboard-metrics`).
  - Latência média `avg_latency_ms`.
  - Economia `saved_minor`.

## 6. Backup & Restore

- Postgres: snapshots diários + dumps (`pg_dump wa_cost_router > backup.sql`).
- Restaurar: `psql -d wa_cost_router < backup.sql`.

## 7. Incidentes

1. **Falha envio**: consultar `/messages/jobs/{id}` para tentativas.
2. **Erro provider**: health check + fallback (avaliar circuit breaker).
3. **Alerta economia negativa**: revisar rate cards e rules.

## 8. Checklist Pré-Deploy

- [ ] Secrets reforçados e validados antes do deploy ([`20251006-enforce-secret-strength`](../backlog/20251006-enforce-secret-strength.md)).
- [ ] Migrations aplicadas e auditadas nos ambientes existentes ([`20251006-migration-base`](../backlog/20251006-migration-base.md)).
- [ ] Tests de fumaça cobrindo fallback multicanal (bloqueados por [`20251006-circuit-breaker`](../backlog/20251006-circuit-breaker.md) e [`20250210-analytics-dashboard-sync`](../backlog/20250210-analytics-dashboard-sync.md)).
- [ ] Monitoramento protegido e métricas autenticadas ([`20251006-proteger-admin-metrics`](../backlog/20251006-proteger-admin-metrics.md)).
```

### docs/DEPLOYMENT.md
```markdown
# Deployment Guide

## Infraestrutura

- **Aplicação**: FastAPI (8000), worker RQ (opcional), frontend (Nginx).
- **Banco**: Postgres gerenciado (TLS, backups).
- **Cache/Fila**: Redis (AWS ElastiCache / Azure Cache).
- **Proxy**: Nginx/Caddy com TLS (Let’s Encrypt).

## Passo a Passo

1. **Preparar `.env`** com `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `APP_SECRET_KEY`, `STRIPE_SECRET_KEY`, `WA_VERIFY_TOKEN`, `SMTP_*`, etc.
2. **Build & Deploy**
   ```bash
   docker-compose pull
   docker-compose run --rm api alembic upgrade head
   docker-compose up -d api worker web
   ```
3. **Reverse Proxy**
   - TLS + HSTS.
   - Rate limit (100 req/min/org).
   - Headers de segurança (CSP, X-Frame-Options).
4. **CORS/HTTPS**
   - Configurar origens via env (ex: `FRONTEND_URL=https://app.example.com`).
   - Forçar HTTPS via proxy.
5. **Monitoramento**
   - Prometheus + Grafana (coletar `/admin/metrics`).
   - Alertas: erro 5xx >2%, latência >3s, economia negativa.
6. **Observabilidade**
   - Logging estruturado.
   - Traço mínimo de requisições (request_id).
7. **Pós-deploy**
   - Rodar testes de fumaça (curl simulate → send → job).
   - Verificar dashboards e métricas.
   - Garantir backup inicial.

## Dimensionamento Inicial

- API: 1 réplica (2 vCPU, 4GB RAM).
- Worker: 1 réplica (opcional).
- Postgres: db.t3.medium (ou equivalente).
- Redis: cache.t3.micro.

## Planos de rollback

- `docker-compose rollback` (usar tags imutáveis).
- Restaurar backup do banco em caso de migração problemática.
```

### docs/PRICING_BILLING.md
```markdown
# Pricing & Billing (Stripe)

## Objetivo

Implementar cobrança recorrente com medição de uso (mensagens enviadas) e impostos internacionais via Stripe Billing + Stripe Tax.

## Componentes

1. **Produtos/Planos**
   - Plano base (mensal) com franquia de mensagens.
   - Excedentes cobrados via metered billing (`usage_type=metered`).
2. **Eventos de Uso**
   - Registrar cada `MessageJob` (status != failed) como unidade de uso.
   - Endpoint worker ou cron que envia `stripe.UsageRecord.create(...)`.
3. **Webhooks Stripe**
   - Eventos: `invoice.created`, `invoice.paid`, `customer.subscription.updated`, `customer.subscription.deleted`, `checkout.session.completed`.
   - Assinar com `STRIPE_WEBHOOK_SECRET` (config em `Settings`).
4. **Integração Backend**
   - Configurar `STRIPE_SECRET_KEY`.
   - Rotas: `POST /billing/checkout`, `POST /billing/webhook` (a criar).
   - Persistir mapping `organization_id -> stripe_customer_id`.
5. **Impostos**
   - Ativar Stripe Tax; coletar endereço fiscal da org.
   - Aplicar `automatic_tax={"enabled": true}` em invoices.

## Passos

1. Criar produtos e preços no dashboard Stripe.
2. Gerar chaves (secret + webhook).
3. Implementar rotas de checkout/billing.
4. Criar job periódico que consolida uso e envia para Stripe.
5. Validar fluxo end-to-end (checkout → envio → invoice).
6. Configurar notificações de pagamento (e-mail/Slack).

## Considerações

- Lidar com retries de webhook (idempotência com `event_id`).
- Sincronizar status do cliente (bloquear envios em caso de inadimplência).
- Armazenar `price_table_version` utilizado para auditorias de cobrança.
```

### docs/ROADMAP.md
```markdown
# Roadmap

## Fase 1 – Hardening (Mês 1)

- Multi-tenant seguro (providers, routing, webhook).
- Criptografia de credenciais.
- Contratos API/UI alinhados (FE mostra dados corretos).
- Validação de números (E.164) e mascaramento de payloads.

## Fase 2 – Observabilidade & Resiliência (Mês 2)

- Circuit breaker por provedor + métricas Prometheus.
- Rate limiting por org e rota.
- Alertas automáticos (latência, taxa de sucesso, economia negativa).
- Worker assíncrono para envios pesados.

## Fase 3 – Monetização & Governança (Mês 3-4)

- Stripe Billing + Tax (metered).
- RBAC (owner/member) e API keys.
- Portal de integrações (webhooks externos, audit trail).
- Sincronização automática de price tables (fonte oficial Meta/fornecedor).

## Definition of Done (por fase)

- **Fase 1**: teste multi-tenant aprovado, credenciais criptografadas, UI exibe dados corretos.
- **Fase 2**: dashboards Prometheus/Grafana ativos, circuit breaker validado com load test.
- **Fase 3**: cobrança ativa com 2 design partners, logs auditáveis e alertas configurados.

## Dependências

- Migration base (pré-Fase 1).
- Time jurídico para LGPD/contratos (Fase 3).
- Contas de teste Stripe e provedores WhatsApp.
```

### docs/CHANGELOG.md
```markdown
# Changelog

## v0.1.0 (2025-10-06)
- Auditoria inicial do código WA Cost Router.
- Identificados gaps de multi-tenancy, segurança e migrations.
- Criados planos de ação, documentação e roadmap.
```

### docs/CONTRIBUTING.md
```markdown
# Guia de Contribuição

## Workflow

1. Fork/clonar repositório.
2. Criar branch a partir de `main`:
   - `feature/<nome-curto>` para features.
   - `fix/<issue>` para correções.
3. Commit mensagens no formato Conventional Commits (`feat:`, `fix:`, `docs:` etc.).
4. Garantir lint/testes locais (quando disponíveis).
5. Abrir Pull Request:
   - Descrever mudança, passos de teste manual e impacto.
   - Referenciar issues relacionadas.

## Padrões de Código

- **Backend**: seguir PEP8, usar `black`/`isort`. Tipagem opcional (pydantic/typing).
- **Frontend**: `eslint` + `prettier`. Componentes com tipagem TS completa.
- **Tests**: (a criar) – preferir Pytest e Vitest.

## Revisão

- Pelo menos 1 revisor.
- Checklist PR:
  - [ ] Migrations atualizadas/descritas.
  - [ ] Contratos API documentados.
  - [ ] Log/telemetria adicionada se pertinente.
  - [ ] Testes manuais descritos.

## Segurança

- Nunca commitar secrets.
- Usar `.env` local e Vault para produção.
- Reportar vulnerabilidades em canal privado (security@empresa.com).

## Releases

- Usar tags semânticas (`vX.Y.Z`).
- Atualizar `docs/CHANGELOG.md` com cada release.
```

## 16. Diffs Sugeridos (Correções Críticas)

### Filtrar providers por organização
```diff
--- a/backend/app/api/providers.py
+++ b/backend/app/api/providers.py
@@
-    provider = db.query(Provider).filter(Provider.id == data.provider_id).first()
+    provider = db.query(Provider).filter(
+        Provider.id == data.provider_id,
+        Provider.org_id == current_user["org_id"]
+    ).first()
@@
-    provider = db.query(Provider).filter(Provider.id == provider_id).first()
+    provider = db.query(Provider).filter(
+        Provider.id == provider_id,
+        Provider.org_id == current_user["org_id"]
+    ).first()
```

### Restringir RoutingEngine ao tenant
```diff
--- a/backend/app/services/routing_engine.py
+++ b/backend/app/services/routing_engine.py
@@
-        provider = self.db.query(Provider).filter(Provider.id == provider_id).first()
+        provider = self.db.query(Provider).filter(
+            Provider.id == provider_id,
+            Provider.org_id == self.org_id
+        ).first()
@@
-        rates = self.db.query(RateCard, Provider).join(
-            Provider, RateCard.source == Provider.name
-        ).filter(
-            RateCard.country_iso == country_iso,
-            RateCard.category == category,
-            Provider.status == "active",
-        ).order_by(RateCard.unit_cost_minor.asc()).first()
+        rates = (
+            self.db.query(RateCard, Provider)
+            .join(Provider, RateCard.source == Provider.name)
+            .filter(
+                Provider.org_id == self.org_id,
+                RateCard.country_iso == country_iso,
+                RateCard.category == category,
+                Provider.status == "active",
+            )
+            .order_by(RateCard.unit_cost_minor.asc())
+            .first()
+        )
```

### Alinhar contrato `/messages/jobs` com UI
```diff
--- a/backend/app/api/messages.py
+++ b/backend/app/api/messages.py
@@
-    return {
-        "jobs": [
-            {
-                "id": str(job.id),
-                "status": job.status.value,
-                "to_number": job.to_number,
-                "template_id": job.template_id,
-                "country_iso": job.country_iso,
-                "created_at": job.created_at.isoformat()
-            }
-            for job in jobs
-        ]
-    }
+    return [
+        {
+            "id": str(job.id),
+            "status": job.status.value,
+            "to_number": job.to_number,
+            "template_id": job.template_id,
+            "template_category": job.template_category,
+            "country_iso": job.country_iso,
+            "created_at": job.created_at.isoformat(),
+        }
+        for job in jobs
+    ]
```

---

*Fim do relatório do agente técnico.*

## Veja também
- [Visão geral](./README.md)
- [Backlog priorizado](../backlog/README.md)
