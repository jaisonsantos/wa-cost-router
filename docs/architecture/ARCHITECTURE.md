[Docs](../current-cycle/README.md) › [Arquitetura](./ARCHITECTURE.md)
# Arquitetura

```
React SPA --> FastAPI --> PostgreSQL
              |            ^
              v            |
          RoutingEngine    |
              |            |
        ProviderConnector (HTTPX) --> Provedores externos
              |\
              | \__ SandboxProviderConnector (modo dev/CI)
```

- **Frontend** (`src/`): React + React Query, AuthContext.
- **API** (`backend/app/`): módulos `api`, `core`, `models`, `services`.
- **Mensageria**: `RoutingEngine` aplica regras (`routing_rule`) e consulta `RateCard`.
- **Persistência**: `MessageJob`, `DeliveryAttempt`, `CostRecord`, `MessageEvent`.
- **Observabilidade**: `/admin/metrics` (Prometheus), logging padrão.
- **Integrações**: `integrations.py` recebe Webhooks WhatsApp (mapear `org_id`).
- **Sandbox**: quando `SANDBOX_PROVIDERS=true`, `get_connector` retorna `SandboxProviderConnector`, que gera IDs/latências determinísticas e evita chamadas HTTP reais.
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
