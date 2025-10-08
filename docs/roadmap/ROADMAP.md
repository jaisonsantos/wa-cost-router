[Docs](../current-cycle/README.md) › [Roadmap](./ROADMAP.md)
# Roadmap

## Fase 1 – Contatos & Opt-in (Mês 1)

**Objetivo ligado a UC-01 — Gestão de contatos unificada:** consolidar catálogo multi-tenant com consentimento auditável, dados higienizados e contratos alinhados à SPA.

### Resultados esperados

- Estrutura de dados pronta para importar, deduplicar e consultar contatos por organização.
- Fluxos de opt-in e timeline com consentimento mascarado para garantir conformidade.
- UI e API devolvendo campos consistentes para as telas de contatos e disparos.

### Marcos e rastreabilidade

| Marco | Tasks (`NEXT_IMPLEMENTATION_PLAN`) | Backlog relacionado |
| --- | --- | --- |
| Catálogo de contatos multi-tenant operacional | `T1` | [`20251006-migration-base`](../backlog/20251006-migration-base.md), [`20251006-sanitizacao-pii`](../backlog/20251006-sanitizacao-pii.md) |
| Validação de opt-in e timeline por contato | `T2` | [`20251006-sanitizacao-pii`](../backlog/20251006-sanitizacao-pii.md) |
| Contratos API/UI alinhados para contatos e disparos | `T1`, `T2` | [`20251006-validacao-e164`](../backlog/20251006-validacao-e164.md), [`20251006-contratos-api-fe`](../backlog/20251006-contratos-api-fe.md) |

## Fase 2 – Atendimento Multicanal (Mês 2)

**Objetivo ligado a UC-02 — Atendimento multicanal orquestrado:** habilitar roteamento inbound/outbound seguro, observabilidade de SLA e automações de fallback.

### Resultados esperados

- Webhook WhatsApp multi-tenant validando assinatura e mapeando `phone_id → org_id`.
- Circuit breaker, rate limiting e indicadores alinhados ao dashboard operacional.
- Painel de SLA e métricas consumindo dados reais de mensagens e custos.

### Marcos e rastreabilidade

| Marco | Tasks (`NEXT_IMPLEMENTATION_PLAN`) | Backlog relacionado |
| --- | --- | --- |
| Webhook inbound multi-tenant pronto para piloto externo | `T3` | [`20251006-webhook-multi-tenant`](../backlog/20251006-webhook-multi-tenant.md) |
| Circuit breaker + rate limiting aplicados por organização | `T3`, `T4` | [`20251006-circuit-breaker`](../backlog/20251006-circuit-breaker.md), [`20251006-rate-limiting`](../backlog/20251006-rate-limiting.md) |
| Dashboard multicanal alinhado às novas métricas | `T4` | [`20250210-analytics-dashboard-sync`](../backlog/20250210-analytics-dashboard-sync.md), [`20251006-contratos-api-fe`](../backlog/20251006-contratos-api-fe.md) |

## Fase 3 – Governança & Monetização (Mês 3-4)

**Objetivo ligado a UC-03/UC-04 — CRM integrado e oferta white-label:** garantir governança comercial, billing e integrações premium com segurança reforçada.

### Resultados esperados

- Conectores CRM e processamento assíncrono suportando alto volume.
- Tarifação multi-tenant e políticas de billing prontas para design partners.
- Controles de segurança e governança (RBAC, métricas protegidas, secrets fortes) ativados.

### Marcos e rastreabilidade

| Marco | Tasks (`NEXT_IMPLEMENTATION_PLAN`) | Backlog relacionado |
| --- | --- | --- |
| Conectores CRM + offload assíncrono dos envios | `T5` | [`20250210-worker-offload`](../backlog/20250210-worker-offload.md) |
| Governança e branding white-label disponíveis | `T6` | [`20251006-proteger-admin-metrics`](../backlog/20251006-proteger-admin-metrics.md), [`20251006-enforce-secret-strength`](../backlog/20251006-enforce-secret-strength.md) |
| Tarifação customizada por organização publicada | `T6` | [`20250210-rate-card-multitenant`](../backlog/20250210-rate-card-multitenant.md) |

## Definition of Done (por fase)

- **Fase 1 – Contatos & Opt-in**: catálogo multi-tenant sem vazamento de PII, contratos SPA ↔ API revisados e migrações aplicadas nos ambientes legados.
- **Fase 2 – Atendimento Multicanal**: webhook validado com piloto externo, circuit breaker/rate limit monitorados e dashboard refletindo SLAs reais.
- **Fase 3 – Governança & Monetização**: billing ativo com design partners, RBAC/governança auditável e integrações CRM em produção.

## Quadro de dependências críticas

| Lacuna pendente | Natureza | Impacto nos casos de uso | Backlog |
| --- | --- | --- | --- |
| Sanitização de PII em payloads e logs | Segurança | Bloqueia UC-01/UC-02 até que contatos e timelines possam armazenar dados higienizados. | [`20251006-sanitizacao-pii`](../backlog/20251006-sanitizacao-pii.md) |
| Proteção do endpoint `/admin/metrics` | Governança | Impede avanço de UC-04 enquanto métricas sensíveis estiverem públicas. | [`20251006-proteger-admin-metrics`](../backlog/20251006-proteger-admin-metrics.md) |
| Enforce de secrets fortes (`APP_SECRET_KEY`, `JWT_SECRET`) | Segurança | Necessário antes de habilitar billing/RBAC em UC-03/UC-04. | [`20251006-enforce-secret-strength`](../backlog/20251006-enforce-secret-strength.md) |
| Rate limiting por organização | Segurança operacional | Pré-requisito para SLAs multicanal confiáveis em UC-02. | [`20251006-rate-limiting`](../backlog/20251006-rate-limiting.md) |

## Veja também

- [Backlog priorizado](../backlog/README.md)
- [Pricing & Billing](../pricing/PRICING_BILLING.md)
- [Segurança](../security/SECURITY.md)
