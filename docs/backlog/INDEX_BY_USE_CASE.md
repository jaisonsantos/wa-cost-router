# Índice do backlog por caso de uso

Este índice agrupa os cards do backlog ativo conforme os casos de uso rastreados na matriz do ciclo. Consulte o link de status para cruzar a situação atual diretamente com a [matriz de rastreabilidade](../current-cycle/USE_CASE_TRACEABILITY.md).

> Os itens marcados como **P0** compõem o ciclo de contatos/opt-ins e devem ser tratados antes de qualquer entrega de P1/P2.

## UC-01 — Gestão de contatos unificada
- [Sanitização de PII e logs sensíveis](./20251006-sanitizacao-pii.md) — **Pendente · P0** ([status na matriz](../current-cycle/USE_CASE_TRACEABILITY.md#status-uc-01))
- [Validação E.164 em cadastros](./20251006-validacao-e164.md) — **Pendente · P0** ([status na matriz](../current-cycle/USE_CASE_TRACEABILITY.md#status-uc-01))
- [Base de migração multi-tenant](./20251006-migration-base.md) — **Pendente · P0** ([status na matriz](../current-cycle/USE_CASE_TRACEABILITY.md#status-uc-01))

## UC-02 — Atendimento multicanal orquestrado
- [Sincronizar dashboard de analytics](./20250210-analytics-dashboard-sync.md) — **Pendente · P2** ([status na matriz](../current-cycle/USE_CASE_TRACEABILITY.md#status-uc-02))
- [Rate limiting por organização](./20251006-rate-limiting.md) — **Pendente · P2** ([status na matriz](../current-cycle/USE_CASE_TRACEABILITY.md#status-uc-02))
- [Contratos API ↔️ Frontend](./20251006-contratos-api-fe.md) — **Pendente · P0** ([status na matriz](../current-cycle/USE_CASE_TRACEABILITY.md#status-uc-02))
- [Hardening multi-tenant do webhook WhatsApp](./20251006-webhook-multi-tenant.md) — **Em andamento · P0** ([status na matriz](../current-cycle/USE_CASE_TRACEABILITY.md#status-uc-02))
- [Circuit breaker por canal](./20251006-circuit-breaker.md) — **Pendente · P1** ([status na matriz](../current-cycle/USE_CASE_TRACEABILITY.md#status-uc-02))

## UC-03 — CRM e jornada integrada
- [Offload de envios para worker RQ](./20250210-worker-offload.md) — **Pendente · P1** ([status na matriz](../current-cycle/USE_CASE_TRACEABILITY.md#status-uc-03))

## UC-04 — Oferta white-label e governança comercial
- [Rate cards por organização](./20250210-rate-card-multitenant.md) — **Pendente · P2** ([status na matriz](../current-cycle/USE_CASE_TRACEABILITY.md#status-uc-04))
- [Proteção de métricas administrativas](./20251006-proteger-admin-metrics.md) — **Pendente · P0** ([status na matriz](../current-cycle/USE_CASE_TRACEABILITY.md#status-uc-04))
- [Enforce secret strength](./20251006-enforce-secret-strength.md) — **Pendente · P0** ([status na matriz](../current-cycle/USE_CASE_TRACEABILITY.md#status-uc-04))
