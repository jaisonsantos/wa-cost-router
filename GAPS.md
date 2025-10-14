# GAPS

## Billing
- Implementar job/metadado para envio de uso metered (`stripe.UsageRecord`) e Stripe Tax conforme plano de pricing; atualmente o backend só atualiza assinatura em webhook sem registrar consumo incremental.【F:docs/pricing/PRICING_BILLING.md†L10-L23】【F:backend/app/api/billing.py†L116-L320】
- Documentar e expor portal de gestão (customer portal) prometido no plano, ou retirar referência até que seja implementado.【F:docs/pricing/PRICING_BILLING.md†L10-L23】

## WABA / Multicanal
- Adicionar conector efetivo para Telegram ou ajustar roadmap/UI para não exibir canal indisponível (apenas display_name existe no catálogo).【F:backend/app/api/integrations.py†L78-L112】【F:backend/app/services/provider_connectors.py†L977-L999】
- Formalizar política de janela de sessão/fallback documentada para WhatsApp → e-mail/Telegram, garantindo timers e monitoramento explícitos no serviço de conversas.【F:backend/app/services/conversations/lifecycle.py†L20-L160】

## CRM
- Completar monitoramento operacional expondo dashboards/endpoint de status por tenant, conforme doc de integrações sugere mas ainda sem implementação de API dedicada.【F:docs/current-cycle/INTEGRATIONS.md†L1-L92】【F:backend/app/services/crm/sync.py†L120-L166】
- Automatizar registro de falhas/dlq para jobs `crm_sync`, evitando perdas silenciosas quando `run_polling_cycle` lança exceções genéricas.【F:backend/app/services/crm/worker.py†L53-L145】

## Compliance
- Executar sanitização retroativa dos logs/tabelas legadas apontada no plano, definindo script/migration e playbook de verificação.【F:docs/current-cycle/NEXT_IMPLEMENTATION_PLAN.md†L45-L69】
- Criar processos automatizados de DSR (export/delete de dados pessoais) além do delete simples de contatos, com auditoria e confirmação ao solicitante.【F:backend/app/api/routes/contacts.py†L204-L288】

## Docs
- Atualizar `docs/api/API_REFERENCE.md` para incluir endpoints de billing (`/billing/checkout`, `/billing/webhook`) e observabilidade `/admin/metrics` com requisitos de header.【F:docs/api/API_REFERENCE.md†L1-L200】【F:backend/app/api/billing.py†L116-L320】【F:backend/app/api/admin.py†L26-L69】
- Ajustar `docs/pricing/PRICING_BILLING.md` removendo temporariamente Stripe Tax/UsageRecord ou marcando como pendente até implementação real.【F:docs/pricing/PRICING_BILLING.md†L8-L23】

## Worker & Resiliência
- Introduzir DLQ/monitoramento para `message_send` e `crm_sync`, permitindo retries diferenciados e inspeção manual de jobs falhos.【F:backend/app/workers/message_send.py†L33-L118】【F:backend/app/services/crm/worker.py†L53-L145】
- Instrumentar métricas de sucesso/falha por provedor com alertas (Grafana/Prometheus) para antecipar degradação de provedores externos.【F:backend/app/services/messages/delivery.py†L355-L617】

## Testes & Qualidade
- Cobrir fluxos de billing no frontend (checkout/alterar plano) com testes automatizados (Playwright ou mock API) para garantir regressão mínima.【F:src/pages/Settings.tsx†L764-L856】【F:tests/e2e/settings-connections.spec.ts†L1-L139】
- Adicionar testes para exportações CSV/JSON no frontend ou Newman, validando headers e conteúdo de `reports/*/export` com cenários multiorganização.【F:backend/app/api/reports.py†L491-L860】
