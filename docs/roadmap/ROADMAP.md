[Docs](../current-cycle/README.md) › [Roadmap](./ROADMAP.md)
# Roadmap

## Fase 1 – Contatos & Opt-in (Mês 1)

**Objetivo ligado a UC-01 — Gestão de contatos unificada:** consolidar catálogo multi-tenant com consentimento auditável, dados higienizados e contratos alinhados à SPA.

### Resultados esperados

- Estrutura de dados pronta para importar, deduplicar e consultar contatos por organização.
- Fluxos de opt-in e timeline com consentimento mascarado para garantir conformidade.
- UI e API devolvendo campos consistentes para as telas de contatos e disparos.

### Marcos e rastreabilidade

| Marco | Status | Tasks (`NEXT_IMPLEMENTATION_PLAN`) | Backlog relacionado |
| --- | --- | --- | --- |
| Catálogo de contatos multi-tenant operacional | ✅ Entregue em 18/10 — ver [Snapshot M1](../history/2024-cycle-contatos-optins/2024-10-18-m1-migracao-api-base.md). | `T1` | [`20251006-migration-base`](../backlog/20251006-migration-base.md), [`20251006-sanitizacao-pii`](../backlog/20251006-sanitizacao-pii.md) |
| Validação de opt-in e timeline por contato | ✅ Entregue em 23/10 — ver [Snapshot M2](../history/2024-cycle-contatos-optins/2024-10-23-m2-timeline-consentimento.md). | `T2` | [`20251006-sanitizacao-pii`](../backlog/20251006-sanitizacao-pii.md) |
| Contratos API/UI alinhados para contatos e disparos | ✅ Entregue em 23/10 — UI e API sincronizadas; sanitização de payloads permanece como follow-up crítico. | `T1`, `T2` | [`20251006-validacao-e164`](../backlog/20251006-validacao-e164.md), [`20251006-contratos-api-fe`](../backlog/20251006-contratos-api-fe.md) |

> **Status da fase:** Concluída para os marcos planejados; sanitização de PII (`20251006-sanitizacao-pii`) segue como bloqueador para o go-live do piloto externo e condiciona a abertura do M3.

## Fase 2 – Atendimento Multicanal (Mês 2)

**Objetivo ligado a UC-02 — Atendimento multicanal orquestrado:** habilitar roteamento inbound/outbound seguro, observabilidade de SLA e automações de fallback.

### Resultados esperados

- Webhook WhatsApp multi-tenant validando assinatura e mapeando `phone_id → org_id`.
- Circuit breaker, rate limiting e indicadores alinhados ao dashboard operacional.
- Painel de SLA e métricas consumindo dados reais de mensagens e custos.

### Marcos e rastreabilidade

| Marco | Status | Tasks (`NEXT_IMPLEMENTATION_PLAN`) | Backlog relacionado |
| --- | --- | --- | --- |
| Webhook inbound multi-tenant pronto para piloto externo | 🚧 Em desenvolvimento — dependente da finalização do mascaramento de payloads e mapeamento `phone_id → org_id` (due 28/10). | `T3` | [`20251006-webhook-multi-tenant`](../backlog/20251006-webhook-multi-tenant.md), [`20251006-sanitizacao-pii`](../backlog/20251006-sanitizacao-pii.md) |
| Circuit breaker + rate limiting aplicados por organização | ⏳ Planejado — aguardando validação do webhook multi-tenant para calibrar thresholds por tenant. | `T3`, `T4` | [`20251006-circuit-breaker`](../backlog/20251006-circuit-breaker.md), [`20251006-rate-limiting`](../backlog/20251006-rate-limiting.md) |
| Dashboard multicanal alinhado às novas métricas | ⏳ Planejado — design de métricas em revisão com squad de analytics após entrega da base de consentimento. | `T4` | [`20250210-analytics-dashboard-sync`](../backlog/20250210-analytics-dashboard-sync.md), [`20251006-contratos-api-fe`](../backlog/20251006-contratos-api-fe.md) |

> **Status da fase:** Em andamento — progresso do webhook multi-tenant determinará a janela de validação dos demais marcos; circuit breaker e rate limiting continuam bloqueados enquanto `20251006-sanitizacao-pii` e `20251006-circuit-breaker` estiverem abertos.

## Fase 3 – Governança & Monetização (Mês 3-4)

**Objetivo ligado a UC-03/UC-04 — CRM integrado e oferta white-label:** garantir governança comercial, billing e integrações premium com segurança reforçada.

### Resultados esperados

- Conectores CRM e processamento assíncrono suportando alto volume.
- Tarifação multi-tenant e políticas de billing prontas para design partners.
- Controles de segurança e governança (RBAC, métricas protegidas, secrets fortes) ativados.

### Marcos e rastreabilidade

| Marco | Status | Tasks (`NEXT_IMPLEMENTATION_PLAN`) | Backlog relacionado |
| --- | --- | --- | --- |
| Conectores CRM + offload assíncrono dos envios | ⏳ Planejado — depende da liberação do piloto externo após M3/M4 e da fila `audit.optin` estabilizada. | `T5` | [`20250210-worker-offload`](../backlog/20250210-worker-offload.md), [`20251006-sanitizacao-pii`](../backlog/20251006-sanitizacao-pii.md) |
| Governança e branding white-label disponíveis | ⏳ Planejado — aguarda hardening de segurança (`/admin/metrics`, secrets fortes) antes do kickoff com parceiros. | `T6` | [`20251006-proteger-admin-metrics`](../backlog/20251006-proteger-admin-metrics.md), [`20251006-enforce-secret-strength`](../backlog/20251006-enforce-secret-strength.md) |
| Tarifação customizada por organização publicada | ⏳ Planejado — depende da validação do circuito multicanal e métricas protegidas. | `T6` | [`20250210-rate-card-multitenant`](../backlog/20250210-rate-card-multitenant.md), [`20251006-circuit-breaker`](../backlog/20251006-circuit-breaker.md) |

> **Status da fase:** Não iniciada — aguardando conclusão das fases anteriores e das frentes de segurança (métricas protegidas, secrets fortes) antes do kickoff com parceiros.

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
