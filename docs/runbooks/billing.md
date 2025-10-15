[Docs](../current-cycle/README.md) › [Runbooks](./) › Billing
# Runbook – Billing (Stripe Tax & Reconciliação)

## Objetivo

Garantir que a cobrança recorrente continue correta após a ativação do Stripe Tax e da reconciliação diária de invoices.
O runbook cobre triagem de falhas em checkout/portal, conferência de impostos e operação dos workers `billing_usage` e `billing_reconcile`.

## Visão Geral

| Item | Descrição |
| --- | --- |
| Componentes | API `backend/app/api/billing.py`, modelos `BillingSubscription`/`BillingInvoice`, workers `billing_usage` e `billing_reconcile`. |
| Métricas | `billing_tax_applied_total{org_id}`, `billing_reconcile_drift{org_id}`, `billing_usage_records_total{org_id,status}`. |
| Filas | `billing_usage`, `billing_reconcile`. |
| Dependências | Stripe Secret/Webhook, Redis, banco PostgreSQL. |

## Procedimentos

### 1. Checkout/Portal com Stripe Tax

1. Verifique se `STRIPE_SECRET_KEY` está definido no `.env` da API/worker.
2. Em caso de erro 5xx ao criar checkout/portal:
   - Consulte logs de `backend` filtrando por `event=billing` ou pela `request_id` correspondente.
   - Reaplique o comando `POST /billing/checkout` ou `POST /billing/portal` (ver exemplos em `docs/api/API_REFERENCE.md`).
3. Confirme que o evento `checkout.session.completed` criou/atualizou `billing_invoice`:
   ```sql
   select stripe_invoice_id, tax_amount_total_minor, currency
   from billing_invoice
   where org_id = '<org_uuid>'
   order by issued_at desc limit 5;
   ```
4. Métrica `billing_tax_applied_total{org_id}` deve refletir o acumulado mais recente (minor units). Se permanecer em zero após invoice paga, valide se o webhook Stripe chegou (`/billing/webhook`).

### 2. Reconciliação diária de invoices

1. O worker roda em `billing_reconcile`. Para execução manual:
   ```python
   from app.workers.billing_reconcile import process_billing_reconciliation
   from datetime import datetime, timedelta, timezone

   process_billing_reconciliation(
       since=datetime.now(timezone.utc) - timedelta(days=1),
       until=datetime.now(timezone.utc)
   )
   ```
2. Verifique logs:
   - `event=billing_reconcile_batch` → resumo (processed/alerts/max_drift_pct).
   - `event=billing_reconcile_item` → por invoice (nível INFO para ok, WARNING se `drift_pct > 1`).
3. Métrica `billing_reconcile_drift{org_id}` deve ficar ≤1. Configure alerta >1 para investigação (diferença >1%).
4. Caso haja divergência:
   - Compare totais locais vs. Stripe (Invoice → Preview → Download PDF).
   - Ajuste manualmente a invoice no Stripe ou reprocessar webhook (Stripe CLI `stripe trigger invoice.paid --id <invoice_id>`).
   - Após ajuste, reexecute o worker para confirmar que `drift_pct` voltou a 0.

### 3. Worker `billing_usage`

Segue inalterado, mas a reconciliação depende dos dados de usage coerentes. Em caso de inconsistências de imposto e consumo, valide se `billing_usage_window` está em `succeeded`.

## Checklist pós-incidente

- [ ] Confirmar que todos os webhooks Stripe (checkout, subscription, invoice) retornam 200.
- [ ] Métricas `billing_tax_applied_total` e `billing_reconcile_drift` estabilizadas (sem valores fora do esperado).
- [ ] Tickets/documentos de cobrança atualizados com causa raiz e ação corretiva.
- [ ] Runbook revisto/atualizado com lições aprendidas, se necessário.

## Referências

- [API Billing](../api/API_REFERENCE.md#billing)
- [Pricing & Billing](../pricing/PRICING_BILLING.md)
- [Workers](../operations/OPERATIONS.md)
