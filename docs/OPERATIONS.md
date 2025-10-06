# Operações & Runbooks

## 1. Migrations

```bash
docker-compose run --rm api alembic history
docker-compose run --rm api alembic upgrade head
```

- Em banco vazio: rodar migration base antes de iniciar API.
- Verificar constraints: `docker-compose exec db psql -U postgres -d wa_cost_router -c "\d message_job"`.

## 2. Seed

- `python scripts/seed.py` cria org demo + dados sintéticos (usa `metadata.create_all` – substituir por migrations futuras).
- `python scripts/seed_providers.py` precisa receber `org_id` válido.

## 3. Saúde

- `GET /admin/health` (após proteger) para readiness.
- `POST /providers/{id}/health` para conectividade com provedores.

## 4. Logs & Monitoramento

- Uvicorn logs stdout; configurar agregador (ELK/CloudWatch).
- Prometheus: `/admin/metrics` (contagem `app_requests_total`).

## 5. Métricas

- Key KPIs:
  - Taxa de sucesso `success_rate` (`/reports/dashboard-metrics`).
  - Latência média `avg_latency_ms`.
  - Economia `saved_minor`.

## 6. Backup & Restore

- Postgres: snapshots diários + dumps (`pg_dump wa_cost_router > backup.sql`).
- Restaurar: `psql -d wa_cost_router < backup.sql`.

## 7. Incidentes

1. **Falha envio**: consultar `/messages/jobs/{id}` para tentativas.
2. **Erro provider**: health check + fallback (avaliar circuit breaker).
3. **Alerta economia negativa**: revisar rate cards e rules.

## 8. Checklist Pré-Deploy

- Secrets preenchidos.
- Migrations aplicadas.
- Tests de fumaça (login, providers, simulate, send).
- Monitoramento ativo.
