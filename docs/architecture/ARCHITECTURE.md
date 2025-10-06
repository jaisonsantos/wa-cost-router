[Docs](../overview/README.md) › [Arquitetura](./ARCHITECTURE.md)
# Arquitetura

```
React SPA --> FastAPI --> PostgreSQL
              |            ^
              v            |
          RoutingEngine    |
              |            |
        ProviderConnector (HTTPX) --> Provedores externos
```

- **Frontend** (`src/`): React + React Query, AuthContext.
- **API** (`backend/app/`): módulos `api`, `core`, `models`, `services`.
- **Mensageria**: `RoutingEngine` aplica regras (`routing_rule`) e consulta `RateCard`.
- **Persistência**: `MessageJob`, `DeliveryAttempt`, `CostRecord`, `MessageEvent`.
- **Observabilidade**: `/admin/metrics` (Prometheus), logging padrão.
- **Integrações**: `integrations.py` recebe Webhooks WhatsApp (mapear `org_id`).
- **Trabalhos assíncronos**: `worker.py` (Redis + RQ) pronto para offloading futuro.

Fluxo de envio:
1. `POST /messages/send` cria `MessageJob`.
2. `RoutingEngine.select_provider()` -> `ProviderCredential` -> `ProviderConnector.send_message()`.
3. `DeliveryAttempt` + `CostRecord`.
4. Job atualizado (delivered/delivered_with_fallback/failed_final).

## Veja também

- [Modelagem de dados](./DATA_MODEL.md)
- [Referência da API](../api/API_REFERENCE.md)
- [Operações](../operations/OPERATIONS.md)
