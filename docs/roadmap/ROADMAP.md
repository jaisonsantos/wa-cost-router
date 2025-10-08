[Docs](../current-cycle/README.md) › [Roadmap](./ROADMAP.md)
# Roadmap

## Fase 1 – Hardening (Mês 1)

- Multi-tenant seguro (providers, routing, webhook).
- Criptografia de credenciais.
- Contratos API/UI alinhados (FE mostra dados reais).
- Validação de números (E.164) e mascaramento de payloads.

## Fase 2 – Observabilidade & Resiliência (Mês 2)

- Circuit breaker por provedor + métricas Prometheus.
- Rate limiting por org e rota.
- Alertas automáticos (latência, taxa de sucesso, economia negativa).
- Worker assíncrono para envios pesados.

## Fase 3 – Monetização & Governança (Mês 3-4)

- Stripe Billing + Tax (metered).
- RBAC (owner/member) e API keys.
- Portal de integrações (webhooks externos, audit trail).
- Sincronização automática de price tables (fonte oficial Meta/fornecedor).

## Definition of Done (por fase)

- **Fase 1**: teste multi-tenant aprovado, credenciais criptografadas, UI exibe dados corretos.
- **Fase 2**: dashboards Prometheus/Grafana ativos, circuit breaker validado com load test.
- **Fase 3**: cobrança ativa com 2 design partners, logs auditáveis e alertas configurados.

## Dependências

- Migration base (pré-Fase 1).
- Time jurídico para LGPD/contratos (Fase 3).
- Contas de teste Stripe e provedores WhatsApp.

## Veja também

- [Backlog priorizado](../backlog/README.md)
- [Pricing & Billing](../pricing/PRICING_BILLING.md)
- [Segurança](../security/SECURITY.md)
