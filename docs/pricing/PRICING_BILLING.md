[Docs](../current-cycle/README.md) › [Pricing](./PRICING_BILLING.md)
# Pricing & Billing (Stripe)

## Objetivo

Implementar cobrança recorrente com medição de uso (mensagens enviadas) e impostos internacionais via Stripe Billing + Stripe Tax.

## Componentes

1. **Produtos/Planos**
   - Plano base (mensal) com franquia de mensagens.
   - Excedentes cobrados via metered billing (`usage_type=metered`).
2. **Eventos de Uso**
   - Registrar cada `MessageJob` (status != failed) como unidade de uso.
   - Endpoint worker ou cron que envia `stripe.UsageRecord.create(...)`.
3. **Webhooks Stripe**
   - Eventos: `invoice.created`, `invoice.paid`, `customer.subscription.updated`, `customer.subscription.deleted`, `checkout.session.completed`.
   - Assinar com `STRIPE_WEBHOOK_SECRET` (config em `Settings`).
4. **Integração Backend**
   - Configurar `STRIPE_SECRET_KEY`.
   - Rotas: `POST /billing/checkout`, `POST /billing/webhook` (a criar).
   - Persistir mapping `organization_id -> stripe_customer_id`.
5. **Impostos**
   - Ativar Stripe Tax; coletar endereço fiscal da org.
   - Aplicar `automatic_tax={"enabled": true}` em invoices.

## Passos

1. Criar produtos e preços no dashboard Stripe.
2. Gerar chaves (secret + webhook).
3. Implementar rotas de checkout/billing.
4. Criar job periódico que consolida uso e envia para Stripe.
5. Validar fluxo end-to-end (checkout → envio → invoice).
6. Configurar notificações de pagamento (e-mail/Slack).

## Considerações

- Lidar com retries de webhook (idempotência com `event_id`).
- Sincronizar status do cliente (bloquear envios em caso de inadimplência).
- Armazenar `price_table_version` utilizado para auditorias de cobrança.

## Veja também

- [Roadmap](../roadmap/ROADMAP.md)
- [Backlog priorizado](../backlog/README.md)
- [Referência da API](../api/API_REFERENCE.md)
