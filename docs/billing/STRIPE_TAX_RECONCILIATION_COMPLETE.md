# Stripe Tax & Reconciliation — Implementação Concluída

Data: 2025-10-16

Resumo:
- Stripe Tax (`automatic_tax`) habilitado nas rotas de checkout e portal (`backend/app/api/billing.py`).
- Webhooks (`checkout.session.completed`, `invoice.paid`) persistem `tax_amount_total_minor` em `billing_invoice` e acumulam em `billing_subscription.tax_amount_total_minor`.
- Worker `billing_reconcile` (fila `billing_reconcile`) compara invoices locais com Stripe e registra `billing_reconcile_drift{org_id}`; emites alerta quando divergência >1%.
- Métricas Prometheus: `billing_tax_applied_total{org_id}`, `billing_reconcile_drift{org_id}` (implementado em `backend/app/metrics.py`).

Arquivos-chave:
- backend/app/api/billing.py
- backend/app/models/models.py
- backend/app/workers/billing_reconcile.py
- backend/app/metrics.py
- backend/tests/test_billing_tax.py
- backend/tests/test_billing_reconcile.py
- docs/pricing/PRICING_BILLING.md
- docs/runbooks/billing.md

Testes:
- Unit/integration tests added for tax persistence and reconciliation (mock Stripe) in `backend/tests`.

Migração:
- Alembic migration `backend/alembic/versions/017_billing_tax_and_invoices.py` cria a tabela `billing_invoice` e coluna `tax_amount_total_minor`.

Observações operacionais:
- Garantir `STRIPE_SECRET_KEY` e `STRIPE_WEBHOOK_SECRET` configurados nos ambientes de staging/production.
- Agendar execução diária do worker `billing_reconcile` via RQ Scheduler ou cron apontando ao worker (fila `billing_reconcile`).

Rollback:
- Reverter a migration `017_billing_tax_and_invoices` com `alembic downgrade <rev>` para remover as tabelas/colunas adicionadas.
