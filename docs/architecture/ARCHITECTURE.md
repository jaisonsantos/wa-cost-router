[Docs](../current-cycle/README.md) › [Arquitetura](./ARCHITECTURE.md)
# Arquitetura

```
React SPA --> FastAPI --> PostgreSQL
              |            ^
              v            |
          RoutingEngine    |
              |
    CircuitBreakerStore <-- Redis
              |
        ProviderConnector (HTTPX) --> Provedores externos
              |\
              | \__ SandboxProviderConnector (modo dev/CI)
```

- **Frontend** (`src/`): React + React Query, AuthContext.
- **API** (`backend/app/`): módulos `api`, `core`, `models`, `services`.
- **Mensageria**: `RoutingEngine` aplica regras (`routing_rule`) e consulta `RateCard`.
- **Persistência**: `MessageJob`, `DeliveryAttempt`, `CostRecord`, `MessageEvent`.
- **Observabilidade**: `/admin/metrics` (Prometheus), logging padrão, gauges de circuit breaker compartilhados.
- **Resiliência**: `CircuitBreakerStore` persiste falhas de provedores em Redis (`circuit:{provider_id}`) e influencia o `RoutingEngine`.
- **Integrações**: `integrations.py` recebe Webhooks WhatsApp (mapear `org_id`).
- **Sandbox**: quando `SANDBOX_PROVIDERS=true`, `get_connector` retorna `SandboxProviderConnector`, que gera IDs/latências determinísticas e evita chamadas HTTP reais.
- **Trabalhos assíncronos**: `worker.py` (Redis + RQ) pronto para offloading futuro.

## Multicanal & Consentimento

- **Resolver de consentimento** — `MultiChannelConsentResolver` agrega estado de `contact_channel_opt_in` por canal/endereço,
  validando preferências antes de cada envio. Ele consulta `ContactPreferenceResolver` e audita violações em
  `contact_consent_audit`.
- **Serviço de opt-in** — `ConsentService` e `OptInRequestService` registram novas concessões, reprocessam confirmações inbound e
  orquestram follow-ups automáticos quando um webhook inbound chega sem consentimento.
- **Normalização de canais** — `PHONE_CHANNELS` cobre `whatsapp` e `sms`; endereços são normalizados (`E.164`/e-mail) em
  `messages.py` para garantir idempotência e roteamento consistente por tenant.
- **Auditoria** — cada transição de consentimento gera versões imutáveis com `proof_hash`/`evidence_uri`, acessíveis pela API e
  pelos dashboards operacionais.

## Fluxo outbound

1. `POST /messages/send` cria `MessageJob`.
2. `RoutingEngine.select_provider()` consulta `CircuitBreakerStore` (ignorando estados `open`/`half-open`) -> `ProviderCredential` -> `ProviderConnector.send_message()`.
3. `CircuitBreakerStore` é atualizado conforme sucesso/falha; `DeliveryAttempt` + `CostRecord` são persistidos.
4. Job atualizado (delivered/delivered_with_fallback/failed_final) e métricas/ logs são emitidos.

## Fluxo inbound multicanal

1. **Webhooks** — `integrations.py` (WhatsApp) e `integrations_sms.py` (SMS) validam assinatura (`X-Hub-Signature-256` ou
   `X-Twilio-Signature`), identificam o tenant (`phone_id`, `To`/`MessagingServiceSid`) e mascaram payload sensível.
2. **Consentimento** — `MultiChannelConsentResolver` verifica opt-in ativo para o endereço informado. Sem consentimento o evento
   é negado (`status=denied`) e um follow-up é enfileirado para solicitar opt-in.
3. **Persistência** — eventos aceitos criam `MessageEvent` (`channel`, `direction`, `delivery_status`) e notificam
   `ConversationLifecycleService` para atualizar `queue_entry`/`sla_snapshot`.
4. **Observabilidade** — métricas Prometheus (`sla_first_response_*`, `messages_delivery_attempts_total`) e logs estruturados
   refletem cada decisão de consentimento ou fallback.

## SLAs e filas

- `ConversationLifecycleService` orquestra estados de conversa (aberta/pending/closed) e alimenta `queue_entry` para relatórios
  de backlog.
- `ConversationMetricsService` agrega tempo de primeira resposta, volume de conversas e taxa de cumprimento, persistindo em
  `sla_snapshot` (por `org_id` + canal + período).
- APIs `/reports/channel-metrics` e `/reports/queues` consomem essas estruturas para expor indicadores operacionais, enquanto o
  dashboard React lê `/reports/dashboard-metrics` e `/reports/provider-metrics` para combinar SLA com custos e economia.

## Veja também

- [Modelagem de dados](./DATA_MODEL.md)
- [Referência da API](../api/API_REFERENCE.md)
- [Operações](../operations/OPERATIONS.md)
