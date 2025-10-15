[Docs](../current-cycle/README.md) › [Pricing](./PRICING_BILLING.md)
# Pricing & Billing (Stripe)

## Objetivo

Registrar consumo metered de mensagens WhatsApp/SMS no Stripe Billing usando `UsageRecord`, garantindo idempotência por janela diária, retries com backoff e observabilidade operacional.

## Componentes

1. **Produtos/Planos**
   - Planos mensais com franquia (`price.metadata.message_quota`).
   - Excedentes faturados como `usage_type=metered` vinculados a `subscription_item_id` persistido em `billing_subscription.stripe_subscription_item_id`.
2. **Eventos de Uso**
   - Cada `MessageEvent` outbound bem-sucedido é marcado como `is_billable` pelo `MessageDeliveryService`.
   - Janelas diárias são materializadas em `billing_usage_window` com status (`pending`, `processing`, `succeeded`, `failed`) e `retry_count`.
3. **Worker `billing_usage`**
   - Processa até `BILLING_USAGE_BATCH_SIZE` janelas por execução.
   - Chama `stripe.UsageRecord.create` com `action=set` e `idempotency_key=usage:<org>:<period_start>:<period_end>`.
   - Retries calculados via `BILLING_USAGE_RETRY_BASE_SECONDS`/`BILLING_USAGE_RETRY_MAX_SECONDS` (exponential backoff) até `BILLING_USAGE_MAX_RETRIES`.
   - Métrica Prometheus `billing_usage_records_total{org_id,status}` e logs estruturados (`billing_usage_synced`, `billing_usage_sync_failure`).
4. **Interface Operacional**
   - Endpoint `POST /billing/usage/sync` agenda sincronização manual.
   - Flag de feature `BILLING_USAGE_SYNC_ENABLED` desliga o worker em ambientes sem Stripe real.
5. **Webhooks Stripe**
   - `customer.subscription.updated` atualiza `stripe_subscription_item_id`, quotas e `current_period_end`.
   - `invoice.paid` sincroniza consumo (para conferência com UsageRecord).

## Fluxo

1. Entrega de mensagem → `MessageEvent` criado → serviço marca `is_billable=True` e agenda a janela.
2. Worker (`rq queue billing_usage`) ou endpoint manual invoca `process_billing_usage_sync`.
3. Serviço `BillingUsageService` agrega eventos por janela (`count(MessageEvent.id)`), envia UsageRecord com `action=set` e atualiza `billing_usage_window`.
4. Falhas transitórias mantêm a janela em `failed` com `next_run_at` calculado; falhas permanentes após `BILLING_USAGE_MAX_RETRIES` requerem intervenção manual.
5. Métricas expostas em `/admin/metrics` permitem dashboards/alertas.

## Configuração

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `STRIPE_SECRET_KEY` | `""` | Obrigatório para enviar UsageRecord; se vazio o worker permanece desabilitado. |
| `BILLING_USAGE_SYNC_ENABLED` | `false` | Habilita o worker e o endpoint de sincronização. |
| `BILLING_USAGE_LOOKBACK_DAYS` | `7` | Janelas diárias criadas retroativamente a partir do `now`. |
| `BILLING_USAGE_GRACE_MINUTES` | `30` | Delay após `period_end` antes de tentar sincronizar (evita reprocessar o dia em curso). |
| `BILLING_USAGE_BATCH_SIZE` | `100` | Limite de janelas processadas por job. |
| `BILLING_USAGE_MAX_RETRIES` | `5` | Tentativas antes de marcar janela como falha permanente. |
| `BILLING_USAGE_RETRY_BASE_SECONDS` | `120` | Delay inicial para retries exponenciais. |
| `BILLING_USAGE_RETRY_MAX_SECONDS` | `3600` | Teto do backoff exponencial. |

## Considerações Operacionais

- Janelas em `failed` com `next_run_at=NULL` indicam necessidade de correção manual (ex.: configurar `stripe_subscription_item_id`).
- `POST /billing/usage/sync` retorna `202` com `job_id` — consultar RQ dashboard para progresso.
- Para auditoria, consultar `billing_usage_window.last_synced_quantity` + Stripe `Upcoming Invoice`.

## Veja também

- [Roadmap](../roadmap/ROADMAP.md)
- [Backlog priorizado](../backlog/README.md)
- [Referência da API](../api/API_REFERENCE.md)
