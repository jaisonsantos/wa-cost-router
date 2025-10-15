# TASKS

1. **Fortalecer monitoramento do conector WhatsApp Cloud**  
   • Prioridade: P0  
   • Área: BE  
   • Dependências: Nenhuma  
   • Estimativa: M  
   • Risco/Impacto: Falhas silenciosas no canal principal geram SLA negativo e perda de savings.  
   • DoD:
     - Adicionar métricas de sucesso/falha e latência específicas do WhatsApp Cloud em Prometheus.
     - Cobrir cenários de erro com testes automatizados (mock HTTPX) e validar logs estruturados.
     - Atualizar runbook para incluir passo a passo de troubleshooting do conector.
   • Branch sugerida: `feat/monitor-wa-cloud`  
   • Título PR sugerido: `feat: melhorar observabilidade do conector WhatsApp Cloud`

2. **Criar DLQ e alertas para o worker de mensagens**  
   • Prioridade: P0  
   • Área: INF  
   • Dependências: Tarefa 1 (reaproveitar métricas).  
   • Estimativa: M  
   • Risco/Impacto: Jobs perdidos comprometem SLA e podem violar contratos de entrega.  
   • DoD:
     - Configurar fila `message_send_dead` com reprocessamento manual documentado.
     - Publicar métricas/alertas (Grafana/Prometheus) para jobs movidos à DLQ.
     - Documentar procedimento de recuperação no runbook de operações.
   • Branch sugerida: `chore/message-send-dlq`  
   • Título PR sugerido: `chore: adicionar DLQ e alarmes para message_send`

3. **Registrar uso metered no Stripe Billing** — ✅ Concluída em 2025-10-14
   • Prioridade: P0
   • Área: BE
   • Dependências: Nenhuma
   • Estimativa: M
   • Risco/Impacto: Sem usage records, faturamento não reflete mensagens reais.
   • DoD:
     - Implementar job/worker que envia `stripe.UsageRecord.create` para cada `MessageJob` concluído.
     - Cobrir retries idempotentes e logs de falha.
     - Atualizar testes de billing simulando invoice com consumo.
   • Branch sugerida: `feat/stripe-usage-record`
   • Título PR sugerido: `feat: registrar consumo metered no Stripe`
   • Resumo: billing_usage worker criado com janelas idempotentes, métricas Prometheus e endpoint `/billing/usage/sync`; message delivery marca eventos faturáveis sem bloquear fluxo e o feature flag só ativa o worker quando `STRIPE_SECRET_KEY` está configurado.
   • Commits/arquivos-chave: backend/app/services/billing/usage.py, backend/app/workers/billing_usage.py, backend/tests/test_billing_usage.py, backend/alembic/versions/016_billing_usage.py, docs/pricing/PRICING_BILLING.md.
   • Notas de migração/rollback: aplicar `alembic upgrade head` para criar `billing_usage_window`/colunas novas; rollback via `alembic downgrade 015_routed_action_dry_run_flag` remove tabela e campos.

4. **Formalizar sanitização retroativa de PII**  
   • Prioridade: P0  
   • Área: COMP  
   • Dependências: Nenhuma  
   • Estimativa: M  
   • Risco/Impacto: Dados sensíveis históricos permanecem expostos em logs/tabelas.  
   • DoD:
     - Levantar tabelas/logs contendo PII legada e definir estratégia de limpeza/masking.
     - Implementar script/migration com dry-run e logs detalhados.
     - Registrar validação e plano de rollback nos playbooks de segurança.
   • Branch sugerida: `chore/purge-legacy-pii`  
   • Título PR sugerido: `chore: sanitizar payloads legados com PII`

5. **Atualizar proteção e observabilidade de `/admin/metrics`**  
   • Prioridade: P0  
   • Área: INF  
   • Dependências: Nenhuma  
   • Estimativa: S  
   • Risco/Impacto: Endpoint crítico pode ficar exposto sem monitoramento.  
   • DoD:
     - Adicionar auditoria de acessos (logs estruturados) com origem e resultado.
     - Configurar alerta para 401/403 recorrentes indicando scans indevidos.
     - Atualizar documentação com instruções de rotação do token admin.
   • Branch sugerida: `chore/admin-metrics-hardening`  
   • Título PR sugerido: `chore: endurecer segurança e logging do /admin/metrics`

6. **Cobrir exportações de relatórios com testes automatizados**  
   • Prioridade: P0  
   • Área: QA  
   • Dependências: Nenhuma  
   • Estimativa: S  
   • Risco/Impacto: Exportações podem quebrar silenciosamente, afetando ROI reports.  
   • DoD:
     - Criar testes Newman/Vitest para `/reports/*/export` validando headers e conteúdo CSV/JSON.
     - Incluir cenários com múltiplos `org_id` para garantir isolamento.
     - Atualizar pipeline `make ci` para executar novos testes.
   • Branch sugerida: `test/reports-export`  
   • Título PR sugerido: `test: validar exportações CSV/JSON dos relatórios`

7. **Validar configuração CORS multi-ambiente**  
   • Prioridade: P0  
   • Área: BE  
   • Dependências: Nenhuma  
   • Estimativa: S  
   • Risco/Impacto: Origem incorreta bloqueia UI ou expõe API a domínios indevidos.  
   • DoD:
     - Adicionar testes unitários para `_determine_cors_origins` cobrindo ambientes dev/prod.
     - Documentar exemplos de configuração no README e `.env.example`.
     - Validar behaviour em build Docker (ENV=production) com token inválido.
   • Branch sugerida: `chore/cors-validation`  
   • Título PR sugerido: `chore: garantir configuração segura de CORS`

8. **Monitorar processamento do webhook HubSpot**  
   • Prioridade: P0  
   • Área: BE  
   • Dependências: Tarefa 3 (metrics Stripe) opcional  
   • Estimativa: M  
   • Risco/Impacto: Eventos perdidos prejudicam sincronização CRM e consent ledger.  
   • DoD:
     - Adicionar métricas/alertas para falhas em `handle_webhook_event` (labels por slug/org).
     - Persistir histórico mínimo de eventos rejeitados para diagnóstico (tabela de auditoria/lightweight).
     - Atualizar documentação de integrações com fluxo de monitoramento.
   • Branch sugerida: `feat/hubspot-webhook-monitoring`  
   • Título PR sugerido: `feat: instrumentar monitoramento do webhook HubSpot`

9. **Implementar conector Telegram ou remover do catálogo**  
   • Prioridade: P1  
   • Área: BE  
   • Dependências: Nenhuma  
   • Estimativa: M  
   • Risco/Impacto: UI promete canal inexistente, gerando frustração no onboarding.  
   • DoD:
     - Avaliar viabilidade de implementar conector (send/health) ou retirar canal da API/UI.
     - Ajustar seeds e schema de providers conforme decisão.
     - Atualizar documentação e testes Playwright.
   • Branch sugerida: `feat/telegram-connector`  
   • Título PR sugerido: `feat: alinhar suporte ao canal Telegram`

10. **Implementar procedimentos DSR automatizados**  
    • Prioridade: P1  
    • Área: COMP  
    • Dependências: Tarefa 4  
    • Estimativa: M  
    • Risco/Impacto: Não conformidade LGPD/GDPR em solicitações de titulares.  
    • DoD:
      - Criar endpoints/rotinas para exportação e remoção auditada por `org_id`.
      - Registrar auditoria de atendimento (quem executou, quando, resultado).
      - Atualizar política de privacidade/documentação operacional.
    • Branch sugerida: `feat/dsr-automation`  
    • Título PR sugerido: `feat: automatizar atendimento a DSR`

11. **Dashboard operacional para `crm_sync`**  
    • Prioridade: P1  
    • Área: INF  
    • Dependências: Tarefas 2 e 8  
    • Estimativa: M  
    • Risco/Impacto: Falhas de sincronização passam despercebidas.  
    • DoD:
      - Expor endpoint `/integrations/crm/status` consolidando último cursor, erros e fila pendente.
      - Publicar painel Grafana com métricas de sucesso/falha por provedor.
      - Documentar checklist operacional.
    • Branch sugerida: `feat/crm-sync-dashboard`  
    • Título PR sugerido: `feat: publicar status operacional de crm_sync`

12. **Atualizar documentação de API e pricing**
    • Prioridade: P1
    • Área: DOC
    • Dependências: Tarefas 3 e 5
    • Estimativa: S
    • Risco/Impacto: Clientes e equipe interna operam com informações desatualizadas.
    • DoD:
      - Adicionar seções de billing/admin metrics na referência de API.
      - Sincronizar `docs/pricing/PRICING_BILLING.md` com features atuais (ou marcar como roadmap).
      - Atualizar README com comandos e novas métricas.
    • Branch sugerida: `docs/update-api-pricing`
    • Título PR sugerido: `docs: alinhar referência de API e pricing`

13. **Regularizar billing do GitHub Actions** — 🚫 Bloqueada (aguardando financeiro)
    • Prioridade: P0
    • Área: OPS
    • Dependências: Nenhuma
    • Estimativa: S
    • Risco/Impacto: Pipelines não executam enquanto o bloqueio persistir, impedindo validação de builds/PRs.
    • DoD:
      - Seguir o [plano de correção](docs/operations/CI_RECOVERY_PLAN.md) para coordenar diagnóstico, mitigação (`make ci-lite`), desbloqueio financeiro e comunicação.
      - Seguir o [runbook de desbloqueio](docs/runbooks/ci_billing.md) para quitar cobranças pendentes ou ajustar o spending limit.
      - Confirmar reativação do GitHub Actions (status "All workflows enabled") nas configurações.
      - Reexecutar workflow (`Re-run jobs`) para validar que os pipelines voltaram a iniciar e anexar recibos/evidências no ticket operacional.
      - Enquanto o bloqueio persistir, rodar `make ci-lite` localmente para gerar `artifacts/ci-lite/summary.json` e anexar o relatório nos PRs críticos como mitigação temporária.
    • Branch sugerida: `ops/github-actions-billing`
    • Título PR sugerido: `ops: desbloquear billing do GitHub Actions`

14. **Testes E2E para fluxo de billing frontend**
    • Prioridade: P1  
    • Área: FE  
    • Dependências: Tarefa 3  
    • Estimativa: M  
    • Risco/Impacto: UI pode quebrar fluxo de checkout/gestão de plano sem detecção.  
    • DoD:
      - Criar cenários Playwright simulando criação de checkout e visualização de assinatura.
      - Mockar respostas Stripe para estados `active`, `past_due` e cancelamento.
      - Integrar testes ao pipeline CI (flag opcional em PRs).
    • Branch sugerida: `test/billing-e2e`  
    • Título PR sugerido: `test: cobrir fluxo de billing no frontend`

15. **Instrumentar métricas por provedor com alertas**
    • Prioridade: P2  
    • Área: INF  
    • Dependências: Tarefas 1 e 2  
    • Estimativa: M  
    • Risco/Impacto: Sem alertas, degradação de provedores só é percebida após impacto no cliente.  
    • DoD:
      - Exportar métricas `messages_delivery_attempts_total` com thresholds e alert rules por provedor.
      - Criar documentação de tuning (limiares e escalonamento).
      - Validar alertas em ambiente de staging.
    • Branch sugerida: `chore/provider-alerts`  
    • Título PR sugerido: `chore: configurar alertas por provedor de mensagem`

16. **Refinar importação de contatos com idempotência expandida**
    • Prioridade: P2
    • Área: BE
    • Dependências: Nenhuma
    • Estimativa: M
    • Risco/Impacto: CSVs repetidos podem gerar duplicidade parcial e ruído de consentimento.
    • DoD:
      - Adicionar chave idempotente por arquivo (`hash`) evitando reprocessamentos acidentais.
      - Melhorar relatório de erros destacando linhas ignoradas por duplicidade.
      - Criar teste cobrindo reenvio do mesmo arquivo.
    • Branch sugerida: `feat/contact-import-idempotency`
    • Título PR sugerido: `feat: reforçar idempotência na importação de contatos`

17. **Stripe Tax automático + reconciliação diária de invoices** — ✅ Concluída em 2025-10-16
    • Prioridade: P0
    • Área: BE
    • Dependências: Nenhuma
    • Estimativa: M
    • Risco/Impacto: Sem Stripe Tax as notas fiscais não contemplavam impostos e divergências com Stripe passavam despercebidas.
    • DoD:
      - Habilitar `automatic_tax` em checkout/portal.
      - Persistir impostos agregados em `billing_invoice` e acumular por organização.
      - Criar worker diário de reconciliação com métricas e alertas.
    • Branch sugerida: `feat/stripe-tax-reconciliation`
    • Título PR sugerido: `feat: habilitar Stripe Tax e reconciliação de invoices`
    • Resumo: checkout/portal agora enviam Stripe Tax, webhooks persistem `tax_amount_total_minor`, novo worker `billing_reconcile` compara invoices locais × Stripe e expõe métricas `billing_tax_applied_total`/`billing_reconcile_drift`.
    • Commits/arquivos-chave: backend/app/api/billing.py, backend/app/models/models.py, backend/app/workers/billing_reconcile.py, backend/tests/test_billing_tax.py, backend/tests/test_billing_reconcile.py, docs/pricing/PRICING_BILLING.md, docs/runbooks/billing.md.
    • Notas de migração/rollback: aplicar `alembic upgrade head` para criar `billing_invoice` e novos campos; rollback via `alembic downgrade 016_billing_usage` remove tabela/colunas.
