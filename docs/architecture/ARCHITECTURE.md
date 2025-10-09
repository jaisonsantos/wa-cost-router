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

Fluxo de envio:
1. `POST /messages/send` cria `MessageJob`.
2. `RoutingEngine.select_provider()` consulta `CircuitBreakerStore` (ignorando estados `open`/`half-open`) -> `ProviderCredential` -> `ProviderConnector.send_message()`.
3. `CircuitBreakerStore` é atualizado conforme sucesso/falha; `DeliveryAttempt` + `CostRecord` são persistidos.
4. Job atualizado (delivered/delivered_with_fallback/failed_final) e métricas/ logs são emitidos.

## Veja também

- [Modelagem de dados](./DATA_MODEL.md)
- [Referência da API](../api/API_REFERENCE.md)
- [Operações](../operations/OPERATIONS.md)
