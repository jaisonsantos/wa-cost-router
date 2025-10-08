# Novo Plano de Implementação — Hardening do Piloto Externo

## Objetivo
Retomar o piloto externo com segurança multi-tenant, garantindo que canais inbound/outbound, contatos e integrações operem sem exposição de dados ou regressões de custo. O plano foca na eliminação dos bloqueadores identificados no pós-mortem e no alinhamento com o roadmap vigente.

## Prioridades imediatas (Out/Nov 2024)
| ID | Entrega | Tipo | Dependências | Critério de sucesso |
| --- | --- | --- | --- | --- |
| P1 | Webhook WhatsApp multi-tenant com roteamento seguro | Backend | [`20251006-webhook-multi-tenant`](../backlog/20251006-webhook-multi-tenant.md) | Eventos inbound isolados por `org_id`, logs sem PII e fallback configurável. |
| P2 | Sanitização de payloads e logs sensíveis | Backend/Security | [`20251006-sanitizacao-pii`](../backlog/20251006-sanitizacao-pii.md) | Campos críticos mascarados em API, banco e observabilidade; checklist de conformidade assinado. |
| P3 | Circuit breaker e rate limiting multicanal | Backend/Platform | [`20251006-circuit-breaker`](../backlog/20251006-circuit-breaker.md) | Política de retry/fallback validada por tenant, métricas em `/admin/metrics` com alerta configurado. |
| P4 | Proteção do endpoint `/admin/metrics` com RBAC | Platform/Security | [`20251006-proteger-admin-metrics`](../backlog/20251006-proteger-admin-metrics.md) | Autenticação aplicada, auditoria de acesso ativa e testes Newman cobrindo cenários de negação. |
| P5 | Catálogo de contatos multi-tenant com timeline | Backend/Data | Dependente de P1 e P2 | CRUD disponível via API, importação CSV com validação de consentimento e backfill controlado. |
| P6 | Dashboard de SLA multicanal alinhado ao backend | Full-stack | Dependente de P1–P5 | Métricas em tempo real exibidas na SPA, com smoke test multicanal documentado. |

## Sequenciamento sugerido
1. **Mitigar riscos P0 (P1–P4):** desbloquear o piloto externo garantindo isolamento de dados e observabilidade protegida.
2. **Concluir base de contatos (P5):** após sanitização e webhook multi-tenant, executar migração do catálogo com monitoramento dedicado.
3. **Habilitar visibilidade operacional (P6):** somente depois que canais e contatos estiverem estáveis, ativar dashboards e alertas multicanal.

## Acompanhamento e rastreabilidade
- A matriz de casos de uso em [`USE_CASE_TRACEABILITY.md`](./USE_CASE_TRACEABILITY.md) deve ser atualizada a cada mudança de status para UC-01 a UC-04.
- Alinhar descobertas adicionais com o backlog priorizado em [`docs/current-cycle/AGENTE.md`](./AGENTE.md) e com o roadmap em [`../roadmap/ROADMAP.md`](../roadmap/ROADMAP.md).
- Referenciar o pós-mortem de planejamento (`NEXT_IMPLEMENTATION_PLAN.md`) ao abrir novos PRs para manter o histórico de decisões.

## Próximos checkpoints
- **D+3:** revisão técnica das implementações P1–P2 com segurança e operações.
- **D+7:** validação integrada de P1–P4 em ambiente de staging (`make dev` + Newman `Messages` + teste `/admin/metrics`).
- **D+10:** go/no-go do piloto externo considerando catálogo de contatos (P5) e preparação do dashboard (P6).

Manter logs de decisão e métricas de rollout anexados a cada checkpoint para facilitar novos pós-mortem e auditorias.
