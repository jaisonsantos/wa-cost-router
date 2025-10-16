Task 3 — Customer Portal (Stripe) backend + botão na UI

**Branch:** `feat/billing-customer-portal`

**What was done:**

* Added backend endpoint `GET /billing/portal` em `backend/app/api/billing.py`.
* Extendido Stripe gateway com `create_billing_portal_session` em `backend/app/services/billing/stripe_client.py`.
* Adicionados testes backend `backend/tests/test_billing_portal.py`.
* Adicionados método `createBillingPortal` em `src/lib/api.ts` e hook `useCreateBillingPortal` em `src/hooks/useApi.ts`.
* Atualizado `src/pages/Settings.tsx` com botão **“Gerenciar assinatura”** e tratamento de loading/errors.
* Adicionado teste E2E Playwright `tests/e2e/billing-portal.spec.ts` que faz mock da URL do portal e valida a navegação.
* Atualizados `docs/api/API_REFERENCE.md` e `README.md` com docs do billing portal e variáveis de ambiente.

**Notes / Migration:**

* Nenhuma migration de DB necessária.
* Garantir `STRIPE_SECRET_KEY` e `STRIPE_WEBHOOK_SECRET` em `backend/.env` para habilitar os fluxos.

**Validation steps:**

* Rodar testes backend: `make test-backend` (ou `pytest backend/tests -q`).
* Rodar E2E frontend: `npm run test:e2e` (Playwright) com a stack no ar.

# TASKS

1. **Fortalecer monitoramento do conector WhatsApp Cloud**
   • Prioridade: P0 • Área: BE • Dependências: Nenhuma • Estimativa: M • Risco/Impacto: Falhas silenciosas no canal principal geram SLA negativo e perda de savings.
   **DoD:**

   * Adicionar métricas de sucesso/falha e latência específicas do WhatsApp Cloud em Prometheus.
   * Cobrir cenários de erro com testes automatizados (mock HTTPX) e validar logs estruturados.
   * Atualizar runbook com troubleshooting do conector.
     **Branch:** `feat/monitor-wa-cloud` • **PR:** `feat: melhorar observabilidade do conector WhatsApp Cloud`

2. **Criar DLQ e alertas para o worker de mensagens**
   • Prioridade: P0 • Área: INF • Dependências: Tarefa 1 • Estimativa: M • Risco/Impacto: Jobs perdidos comprometem SLA e podem violar contratos de entrega.
   **DoD:**

   * Configurar fila `message_send_dead` com reprocessamento manual documentado.
   * Publicar métricas/alertas (Grafana/Prometheus) para jobs movidos à DLQ.
   * Documentar recuperação no runbook de operações.
     **Branch:** `chore/message-send-dlq` • **PR:** `chore: adicionar DLQ e alarmes para message_send`

3. **Registrar uso metered no Stripe Billing** — ✅ Concluída em 2025-10-14
   • Prioridade: P0 • Área: BE • Dependências: Nenhuma • Estimativa: M • Risco/Impacto: Sem usage records, faturamento não reflete mensagens reais.
   **DoD:**

   * Implementar worker que envia `stripe.UsageRecord.create` por `MessageJob` concluído.
   * Cobrir retries idempotentes e logs de falha.
   * Atualizar testes simulando invoice com consumo.
     **Branch:** `feat/stripe-usage-records` • **PR:** `feat: registrar consumo metered no Stripe`
     **Resumo:** `billing_usage` com janelas idempotentes, métricas Prometheus e endpoint `/billing/usage/sync`; delivery marca eventos faturáveis; feature flag ativa com `STRIPE_SECRET_KEY`.
     **Commits/arquivos:** `backend/app/services/billing/usage.py`, `backend/app/workers/billing_usage.py`, `backend/tests/test_billing_usage_unit.py`, `backend/alembic/versions/016_billing_usage.py`, `docs/pricing/PRICING_BILLING.md`.
     **Migração/rollback:** `alembic upgrade head`; rollback para `015_routed_action_dry_run_flag`.

4. **Formalizar sanitização retroativa de PII**
   • Prioridade: P0 • Área: COMP • Estimativa: M • Risco/Impacto: PII histórico exposto.
   **DoD:** mapear tabelas/logs, script/migration com dry-run, registrar validação e rollback.
   **Branch:** `chore/purge-legacy-pii` • **PR:** `chore: sanitizar payloads legados com PII`

5. **Atualizar proteção e observabilidade de `/admin/metrics`**
   • Prioridade: P0 • Área: INF • Estimativa: S • Risco/Impacto: Endpoint crítico exposto.
   **DoD:** auditoria de acessos, alerta para 401/403, doc de rotação de token.
   **Branch:** `chore/admin-metrics-hardening` • **PR:** `chore: endurecer segurança e logging do /admin/metrics`

6. **Cobrir exportações de relatórios com testes automatizados**
   • Prioridade: P0 • Área: QA • Estimativa: S • Risco/Impacto: Export pode quebrar silenciosamente.
   **DoD:** testes Newman/Vitest para `/reports/*/export`, múltiplos `org_id`, integrar no `make ci`.
   **Branch:** `test/reports-export` • **PR:** `test: validar exportações CSV/JSON dos relatórios`

7. **Validar configuração CORS multi-ambiente**
   • Prioridade: P0 • Área: BE • Estimativa: S • Risco/Impacto: UI bloqueada ou API exposta.
   **DoD:** testes para `_determine_cors_origins`, docs no README e `.env.example`, validar build Docker.
   **Branch:** `chore/cors-validation` • **PR:** `chore: garantir configuração segura de CORS`

8. **Monitorar processamento do webhook HubSpot**
   • Prioridade: P0 • Área: BE • Estimativa: M • Risco/Impacto: Eventos perdidos prejudicam sync.
   **DoD:** métricas/alertas por slug/org, histórico mínimo de rejeições, docs de monitoramento.
   **Branch:** `feat/hubspot-webhook-monitoring` • **PR:** `feat: instrumentar monitoramento do webhook HubSpot`

9. **Implementar conector Telegram ou remover do catálogo**
   • Prioridade: P1 • Área: BE • Estimativa: M • Risco/Impacto: UI promete canal inexistente.
   **DoD:** decidir implementar ou remover, ajustar seeds/schema, atualizar docs e Playwright.
   **Branch:** `feat/telegram-connector` • **PR:** `feat: alinhar suporte ao canal Telegram`

10. **Implementar procedimentos DSR automatizados**
    • Prioridade: P1 • Área: COMP • Dependência: Tarefa 4 • Estimativa: M • Risco/Impacto: Risco LGPD/GDPR.
    **DoD:** endpoints/rotinas de export/remoção auditada por `org_id`, auditoria de atendimento, atualizar políticas.
    **Branch:** `feat/dsr-automation` • **PR:** `feat: automatizar atendimento a DSR`

11. **Dashboard operacional para `crm_sync`**
    • Prioridade: P1 • Área: INF • Dependências: Tarefas 2 e 8 • Estimativa: M
    **DoD:** endpoint `/integrations/crm/status`, painel Grafana, checklist operacional.
    **Branch:** `feat/crm-sync-dashboard` • **PR:** `feat: publicar status operacional de crm_sync`

12. **Atualizar documentação de API e pricing**
    • Prioridade: P1 • Área: DOC • Dependências: Tarefas 3 e 5 • Estimativa: S
    **DoD:** seções de billing/admin metrics, sincronizar `PRICING_BILLING.md`, atualizar README.
    **Branch:** `docs/update-api-pricing` • **PR:** `docs: alinhar referência de API e pricing`

13. **Regularizar billing do GitHub Actions** — 🚫 Bloqueada (aguardando financeiro)
    • Prioridade: P0 • Área: OPS • Estimativa: S • Risco/Impacto: Pipelines parados.
    **DoD:** seguir plano de correção e runbook, confirmar reativação, reexecutar workflows; enquanto bloqueado usar `make ci-lite` e `make ci-lite-publish`.
    **Branch:** `ops/github-actions-billing` • **PR:** `ops: desbloquear billing do GitHub Actions`

14. **Testes E2E para fluxo de billing frontend**
    • Prioridade: P1 • Área: FE • Dependências: Tarefa 3 • Estimativa: M
    **DoD:** cenários Playwright para checkout/assinatura, mocks `active/past_due/canceled`, integrar no CI.
    **Branch:** `test/billing-e2e` • **PR:** `test: cobrir fluxo de billing no frontend`

15. **Instrumentar métricas por provedor com alertas**
    • Prioridade: P2 • Área: INF • Dependências: Tarefas 1 e 2 • Estimativa: M
    **DoD:** `messages_delivery_attempts_total` com thresholds/alerts por provedor, docs de tuning, validar em staging.
    **Branch:** `chore/provider-alerts` • **PR:** `chore: configurar alertas por provedor de mensagem`

16. **Refinar importação de contatos com idempotência expandida**
    • Prioridade: P2 • Área: BE • Estimativa: M
    **DoD:** chave idempotente por arquivo (`hash`), relatório de erros melhorado, teste de reenvio.
    **Branch:** `feat/contact-import-idempotency` • **PR:** `feat: reforçar idempotência na importação de contatos`

17. **Stripe Tax automático + reconciliação diária de invoices** — ✅ Concluída em 2025-10-16
    • Prioridade: P0 • Área: BE • Estimativa: M
    **DoD:** habilitar `automatic_tax` em checkout/portal, persistir impostos agregados, worker diário de reconciliação com métricas/alertas.
    **Branch:** `feat/stripe-tax-reconciliation` • **PR:** `feat: habilitar Stripe Tax e reconciliação de invoices`
    **Resumo:** checkout/portal agora enviam Stripe Tax; webhooks persistem `tax_amount_total_minor`; `billing_reconcile` compara invoices locais × Stripe e expõe `billing_tax_applied_total`/`billing_reconcile_drift`.
    **Commits/arquivos:** `backend/app/api/billing.py`, `backend/app/models/models.py`, `backend/app/workers/billing_reconcile.py`, `backend/tests/test_billing_tax.py`, `backend/tests/test_billing_reconcile.py`, `docs/pricing/PRICING_BILLING.md`, `docs/runbooks/billing.md`.
    **Migração/rollback:** `alembic upgrade head`; rollback para `016_billing_usage`.