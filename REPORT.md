# Auditoria WA Cost Router v2

## Sumário executivo
- A API FastAPI agrega módulos de autenticação, mensagens, integrações, billing e relatórios, com CORS parametrizado por ambiente via `API_CORS_ORIGINS`.【F:backend/app/main.py†L4-L103】【F:backend/app/core/config.py†L34-L138】
- O roteamento outbound usa `MessageDeliveryService` assíncrono, circuit breaker em Redis e persiste histórico de `RoutedAction`/`DeliveryAttempt` para auditoria e métricas Prometheus.【F:backend/app/services/messages/delivery.py†L321-L707】
- Enfileiramento assíncrono cobre `message_send`, `crm_sync` e `default` (imports) através de workers RQ compartilhados no bootstrap padrão.【F:backend/app/workers/message_send.py†L25-L118】【F:backend/app/services/crm/worker.py†L20-L145】【F:backend/app/services/contacts/import_worker.py†L28-L198】【F:backend/worker.py†L1-L12】
- Conectores oficiais existem para WhatsApp Cloud, 360Dialog, Gupshup, Twilio e SendGrid; o factory `get_connector` seleciona sandbox ou produção conforme configuração, com suíte dedicada de testes para WhatsApp Cloud.【F:backend/app/services/provider_connectors.py†L380-L999】【F:backend/tests/services/test_whatsapp_cloud_connector.py†L34-L114】
- O catálogo de templates WhatsApp expõe CRUD, sincronização multi-provedor e interface React com filtros, mantendo metadados sanitizados.【F:backend/app/api/templates.py†L87-L312】【F:src/pages/Templates.tsx†L10-L167】
- Endpoints de relatórios oferecem exportação CSV/JSON para métricas financeiras, operacionais e de filas, reutilizando helpers de streaming.【F:backend/app/api/reports.py†L491-L860】
- Billing com Stripe inclui checkout, webhook, parsing de assinaturas e exibição de uso/quota no frontend, validado por testes de integração em memória.【F:backend/app/api/billing.py†L116-L320】【F:backend/tests/test_billing_api.py†L105-L219】【F:src/pages/Settings.tsx†L764-L856】
- `/admin/metrics` requer token administrado e mede contagem de scrapes/circuitos, com testes garantindo respostas 401/403 quando ausente ou inválido.【F:backend/app/api/admin.py†L26-L69】【F:backend/tests/test_admin_metrics_auth.py†L32-L59】
- Sanitização de PII cobre variáveis/template, payloads de provedores e webhooks inbound, mascarando telefones/emails antes de persistir.【F:backend/app/core/pii.py†L52-L190】【F:backend/app/api/messages.py†L277-L289】【F:backend/app/services/messages/delivery.py†L452-L705】【F:backend/app/api/integrations.py†L513-L858】
- Integração CRM suporta HubSpot (webhook + polling) e Pipedrive (polling), com script CLI, fila dedicada e métricas `crm_sync_*` expostas.【F:backend/app/api/integrations_crm.py†L71-L154】【F:backend/app/services/crm/hubspot.py†L14-L191】【F:backend/app/services/crm/pipedrive.py†L17-L188】【F:backend/app/services/crm/sync.py†L34-L166】【F:backend/scripts/run_crm_sync.py†L15-L105】
- Contatos, opt-ins e preferências multi-tenant contam com normalização E.164/email, histórico de auditoria e importação CSV assíncrona com relatórios de erro.【F:backend/app/api/routes/contacts.py†L204-L318】【F:backend/app/services/routing/preferences.py†L52-L175】【F:backend/app/services/contacts/import_worker.py†L52-L198】
- A documentação operacional sinaliza pendências de sanitização retroativa e proteção de métricas ainda abertas no plano do ciclo atual, alinhando backlog a essas lacunas.【F:docs/current-cycle/NEXT_IMPLEMENTATION_PLAN.md†L17-L69】

## 1. Inventário & arquitetura detectada
### Backend / API
- `backend/app/main.py` instancia FastAPI, aplica CORS a partir de `_determine_cors_origins` e registra routers para auth, mensagens, integrações, contatos, templates, billing e admin.【F:backend/app/main.py†L34-L103】
- Configurações centralizadas em `Settings` validam secrets obrigatórios fora de ambientes locais e expõem helper para token de métricas.【F:backend/app/core/config.py†L142-L176】
- `messages.py` trata idempotência (`idempotency_key`), resolve destinatário preferencial via `ContactPreferenceResolver`, calcula baseline vs. custo otimizado e enfileira entregas.【F:backend/app/api/messages.py†L218-L450】
- `RoutingEngine` (não exibido) é utilizado por `MessageDeliveryService` para montar cadeia de fallback, respeitando estados do circuit breaker e tarifação via `RateCard`/`CostRecord`. Persistência de `RoutedAction` garante trilha auditável.【F:backend/app/services/messages/delivery.py†L321-L707】

### Serviços, workers e filas
- Worker principal (`backend/worker.py`) escuta filas `default`, `message_send` e `crm_sync`, utilizando Redis configurável via `settings.REDIS_URL`.【F:backend/worker.py†L1-L12】
- `message_send` worker reconstrói `DeliveryContext`, invoca serviço assíncrono e incrementa métricas Prometheus por provedor/canal.【F:backend/app/workers/message_send.py†L33-L118】
- Fila `crm_sync` agenda polling incremental com guarda de intervalo mínimo e serialização ISO de cursores.【F:backend/app/services/crm/worker.py†L53-L145】
- Importações de contato são processadas na fila `default`, gerando relatórios CSV de erros e atualizando status do job (`ContactImportJob`).【F:backend/app/services/contacts/import_worker.py†L38-L198】

### Conectores e integrações
- `provider_connectors.py` define conectores concretos (360Dialog, Gupshup, WhatsApp Cloud, Twilio, SendGrid) com health-check dedicado, fallback sandbox e método `list_templates` usado no catálogo.【F:backend/app/services/provider_connectors.py†L30-L999】
- Integrações WhatsApp gerenciam conexões multi-tenant (`WAConnection`), health-checks, webhook com validação HMAC e auditoria de consentimento ao negar mensagens sem opt-in.【F:backend/app/api/integrations.py†L198-L858】
- Endpoints CRM (`/integrations/crm/{slug}/webhook|poll`) validam HMAC com `CRM_WEBHOOK_SECRET` e acionam `CRMIncrementalSyncService`, que atualiza cursores em `Provider.meta`.【F:backend/app/api/integrations_crm.py†L71-L154】【F:backend/app/services/crm/sync.py†L120-L166】

### Frontend e contratos
- SPA React utiliza hooks `useTemplates`/`useSyncTemplates` para sincronização de templates e apresenta painéis de billing com consumo, fatura e quota a partir da API de billing.【F:src/pages/Templates.tsx†L10-L167】【F:src/pages/Settings.tsx†L764-L856】
- Tipos compartilhados residem em `src/types/api.ts`, garantindo alinhamento com respostas backend (ex.: `BillingSummaryResponse`).【F:src/types/api.ts†L158-L177】

### Dados, compliance e observabilidade
- Sanitização centralizada em `app/core/pii.py` mascara e-mails/telefones e tokens antes de persistir variables/respostas, sendo reutilizada em mensagens e integrações.【F:backend/app/core/pii.py†L52-L190】【F:backend/app/api/messages.py†L277-L289】
- Conversas inbound alimentam `ConversationLifecycleService`, que controla backlog (`QueueEntry`) e emite métricas de first response para Prometheus.【F:backend/app/services/conversations/lifecycle.py†L20-L160】
- Métricas administrativas incluem contadores de scrapes e estados do circuito, exigindo token específico conforme `settings.get_metrics_auth_token()`.【F:backend/app/api/admin.py†L16-L69】【F:backend/app/core/config.py†L167-L176】

## 2. Checagem contra o “estágio da foto”
| Item | Status | Evidências | Observações |
| --- | --- | --- | --- |
| 1. Conector WhatsApp Cloud outbound | Feito | Classe dedicada, factory e testes de sucesso/falha.【F:backend/app/services/provider_connectors.py†L380-L520】【F:backend/tests/services/test_whatsapp_cloud_connector.py†L34-L114】 | — |
| 2. Auditoria de roteamento (`RoutedAction`) | Feito | Persistência em `MessageDeliveryService` e consulta via `/messages/jobs/{id}/routing`.【F:backend/app/services/messages/delivery.py†L647-L708】【F:backend/app/api/messages.py†L197-L215】【F:backend/app/api/messages.py†L484-L515】 | — |
| 3. Catálogo de templates WhatsApp | Feito | CRUD + sync backend e UI React com filtros/status.【F:backend/app/api/templates.py†L87-L312】【F:src/pages/Templates.tsx†L10-L167】 | — |
| 4. Exportação CSV/JSON em relatórios | Feito | Endpoints `/reports/*/export` aceitam `format=csv|json` e usam helpers de streaming.【F:backend/app/api/reports.py†L491-L860】 | — |
| 5. Stripe billing (checkout/webhook/portal) | Parcial | Checkout e webhook implementados/testados.【F:backend/app/api/billing.py†L116-L320】【F:backend/tests/test_billing_api.py†L105-L219】 | Falta portal de cliente/geração de uso (`UsageRecord`) previsto na documentação de pricing.【F:docs/pricing/PRICING_BILLING.md†L10-L23】 |
| 6. Proteção `/admin/metrics` | Feito | Header dedicado e exceções 401/403 validadas em testes.【F:backend/app/api/admin.py†L26-L69】【F:backend/tests/test_admin_metrics_auth.py†L32-L59】 | — |
| 7. Sanitização de PII | Parcial | Sanitização aplicada a variables, payloads e webhooks.【F:backend/app/core/pii.py†L52-L190】【F:backend/app/api/integrations.py†L513-L858】 | Falta sanitização retroativa de logs indicada como pendência crítica no plano do ciclo.【F:docs/current-cycle/NEXT_IMPLEMENTATION_PLAN.md†L53-L69】 |
| 8. Webhook HubSpot + CRMSyncService | Feito | Verificação HMAC, parse e sync incremental com fallback de polling.【F:backend/app/api/integrations_crm.py†L71-L154】【F:backend/app/services/crm/hubspot.py†L14-L191】 | — |
| 9. Runner & métricas CRM | Feito | `run_crm_sync.py`, fila `crm_sync` e métricas `crm_sync_*`.【F:backend/scripts/run_crm_sync.py†L15-L105】【F:backend/app/services/crm/worker.py†L53-L145】【F:backend/app/services/crm/sync.py†L34-L166】 | — |
| 10. Provider Pipedrive | Feito | Conector dedicado, normalização e testes unitários.【F:backend/app/services/crm/pipedrive.py†L17-L188】【F:backend/tests/services/test_crm_pipedrive.py†L1-L90】 | — |
| 11. Processar envios via fila | Feito | `POST /messages/send` enfileira `DeliveryContext` e worker executa retries/fallbacks.【F:backend/app/api/messages.py†L437-L450】【F:backend/app/workers/message_send.py†L33-L118】 | — |
| 12. CORS parametrizável | Feito | `_determine_cors_origins` combina env + defaults com deduplicação.【F:backend/app/main.py†L34-L60】 | — |
| 13. Bloquear secrets padrão fora de dev | Feito | `Settings.model_post_init` invalida secrets fracos quando `ENVIRONMENT` ≠ local.【F:backend/app/core/config.py†L142-L165】 | — |

## 3. Casos de uso implementados (checklist)
| Caso de uso | Status | Evidências | Notas |
| --- | --- | --- | --- |
| Onboarding & integrações (WABA/Email/SMS/Telegram) | Parcial | Conectores ativos para WhatsApp, SMS (Twilio) e Email (SendGrid); Telegram apenas listado sem conector real.【F:backend/app/services/provider_connectors.py†L30-L705】【F:backend/app/api/integrations.py†L78-L446】 | Implementar conector Telegram ou ajustar documentação que anuncia suporte. |
| Contatos & Consent ledger + Preference Center | Feito | Listagem com filtros, histórico de consentimento e resolução de preferências multi-canal.【F:backend/app/api/routes/contacts.py†L204-L288】【F:backend/app/services/routing/preferences.py†L52-L175】 | — |
| Campanhas & Motor de decisão (custo × entregabilidade × preferências) | Feito | `RoutingEngine` seleciona provedor considerando circuit breaker, custo estimado e consentimento; custos salvos em `CostRecord`.【F:backend/app/services/messages/delivery.py†L327-L519】 | — |
| Fallback/retry/idempotência | Feito | Idempotência por `idempotency_key`, retries exponenciais e fallback chain persistida.【F:backend/app/api/messages.py†L237-L327】【F:backend/app/services/messages/delivery.py†L323-L611】 | — |
| Shadow routing (simulação) | Feito | Endpoint `/messages/jobs/{job_id}/dry-run` reusa serviço de dry-run e grava `RoutedAction` com `dry_run=True`.【F:backend/app/api/messages.py†L517-L563】【F:backend/app/services/messages/delivery.py†L164-L214】 | — |
| Janela de sessão WA e transbordo (email/Telegram) | Parcial | Conversas inbound atualizam `Conversation`/`QueueEntry`; fallback para email existe, mas Telegram ainda não implementado.。【F:backend/app/services/conversations/lifecycle.py†L20-L160】【F:backend/app/services/provider_connectors.py†L600-L705】 | Falta estratégia explícita de janela/expiração e canal Telegram efetivo. |
| Métricas & ROI/savings; exportações | Feito | `DashboardMetrics`, exportações CSV/JSON e cálculo de economia baseline vs. otimizado.【F:backend/app/api/reports.py†L520-L800】 | — |
| Catálogo de templates + multilíngue básico | Feito | Sincronização agrega idiomas/status disponíveis e UI exibe filtros por idioma/status.【F:backend/app/api/templates.py†L246-L320】【F:src/pages/Templates.tsx†L21-L123】 | — |
| Integrações CRM (HubSpot/Pipedrive) | Feito | Conectores + worker + documentação operacional atualizados.【F:backend/app/services/crm/hubspot.py†L14-L191】【F:backend/app/services/crm/pipedrive.py†L17-L188】 | — |
| White-label/multi-tenant | Parcial | APIs segregam por `org_id`, mas branding/tokens white-label ainda não configuráveis na UI conforme roadmap.【F:backend/app/api/messages.py†L280-L344】【F:docs/current-cycle/NEXT_IMPLEMENTATION_PLAN.md†L45-L69】 | Necessário seguir épico governança/branding. |
| Segurança/Compliance (LGPD/GDPR, PII, DSR) | Parcial | PII mascarada e consent ledger ativo; falta sanitização retroativa e procedimentos DSR automatizados (export/delete).【F:backend/app/core/pii.py†L52-L190】【F:docs/current-cycle/NEXT_IMPLEMENTATION_PLAN.md†L53-L69】 | Formalizar processos DSR e limpeza histórica. |
| Escalabilidade (fila, DLQ, throttling, quality rating) | Parcial | Filas e circuit breaker implementados; não há DLQ dedicada ou throttling por provedor além de rate limit por org.【F:backend/app/workers/message_send.py†L33-L118】【F:backend/app/services/messages/delivery.py†L321-L620】 | Avaliar DLQ/monitoramento de qualidade por provedor. |

## 4. Drift de documentação
- `docs/pricing/PRICING_BILLING.md` exige envio de `stripe.UsageRecord` e Stripe Tax (`automatic_tax`), mas o backend não implementa criação de usage records nem configuração de impostos nas sessões de checkout/webhook.【F:docs/pricing/PRICING_BILLING.md†L8-L23】【F:backend/app/api/billing.py†L116-L320】
- Documentação de pricing menciona job periódico de billing que ainda não existe no código ou scripts (`stripe.UsageRecord.create`).【F:docs/pricing/PRICING_BILLING.md†L10-L23】
- A referência de API não descreve endpoints de billing (`/billing/checkout`, `/billing/webhook`), apesar de estarem ativos no backend e usados pelo frontend.【F:backend/app/api/billing.py†L116-L320】【F:docs/api/API_REFERENCE.md†L1-L120】
- Plano do ciclo destaca sanitização retroativa e proteção `/admin/metrics` como pendências; enquanto `/admin/metrics` já está protegido, falta atualização dos docs para refletir o hardening concluído e o gap restante focado em logs históricos.【F:docs/current-cycle/NEXT_IMPLEMENTATION_PLAN.md†L45-L69】【F:backend/app/api/admin.py†L26-L69】

## 5. Billing / Stripe & preços
- Checkout cria clientes Stripe sob demanda, anexa metadados `org_id` e reusa `BillingSubscription` único por organização, atualizando quota/valor a partir do webhook `customer.subscription.updated`.【F:backend/app/api/billing.py†L116-L269】
- Webhook trata `invoice.paid` para atualizar uso (`message_usage`) e URL da fatura, além de persistir status e método de pagamento sanitizado (brand/last4).【F:backend/app/api/billing.py†L270-L320】
- Integração depende de chaves `STRIPE_SECRET_KEY` e `STRIPE_WEBHOOK_SECRET`; o wrapper `StripeGateway` centraliza chamadas e valida configuração antes de permitir operações.【F:backend/app/services/billing/stripe_client.py†L17-L57】
- Seeds e UI não definem planos fixos; valores exibidos derivam do payload Stripe (nickname/amount). Sem job de metered usage ou Stripe Tax conforme planejado, o faturamento cobre apenas assinatura recorrente padrão.【F:backend/scripts/seed.py†L87-L303】【F:docs/pricing/PRICING_BILLING.md†L10-L23】

## 6. Segurança & Compliance
- Secrets frágeis causam falha na inicialização fora de ambientes locais; `.env.example` alerta para substituição de `JWT_SECRET`/`APP_SECRET_KEY` e preserva `ENVIRONMENT=local` por padrão.【F:backend/app/core/config.py†L142-L165】【F:.env.example†L1-L34】
- `/admin/metrics` exige header configurável e retorna 503 quando nenhum token está configurado, prevenindo exposição em produção.【F:backend/app/api/admin.py†L26-L69】
- Sanitização PII cobre contatos, payloads de provedores e webhooks, mas sanitização retroativa de logs permanece aberta conforme backlog.【F:backend/app/core/pii.py†L52-L190】【F:docs/current-cycle/NEXT_IMPLEMENTATION_PLAN.md†L53-L69】
- Consent ledger versiona opt-ins (`ContactConsentAudit`) e bloqueia mensagens inbound sem opt-in, registrando auditoria e reabrindo solicitações via `OptInRequestService`.【F:backend/app/api/integrations.py†L693-L809】
- Não há processo automatizado para pedidos DSR (export/delete) além de APIs de contato padrão; risco residual para compliance LGPD/GDPR. |

## 7. Qualidade & CI
- Makefile oferece `make test-backend` (Pytest), `make lint-backend` (Ruff) e pipeline completo `make ci` com migrations + seed + Newman (Postman).【F:Makefile†L1-L118】
- Suite de testes backend cobre conectores, billing, rate limiting, integrações, métricas e workers (`backend/tests/*`).【F:backend/tests/test_billing_api.py†L105-L219】【F:backend/tests/test_reports_export.py†L1-L160】
- CI GitHub Actions (`ci.yml`) executa lint/testes separados para backend, frontend e fluxo e2e encadeado, reaproveitando `make ci` como etapa principal após build/test unitário.【F:.github/workflows/ci.yml†L1-L118】
- Frontend possui testes Playwright (`tests/e2e`) e contratos TS; entretanto, não há indicação de cobertura automatizada para fluxos de billing no frontend (apenas UI). Avaliar ampliar testes integrados.

