# Operações & Runbooks

## 0. Atalhos do Makefile

Os comandos operacionais agora possuem atalhos via `Makefile` na raiz do projeto.

| Comando | Ação |
| --- | --- |
| `make dev` | Builda e sobe todos os serviços em foreground |
| `make up` / `make down` | Sobe ou derruba a stack em modo detach |
| `make logs`, `make logs-api`, `make logs-db`, `make logs-web` | Tail de logs |
| `make migrate` | Executa `alembic upgrade head` |
| `make seed`, `make seed-providers` | Roda os scripts de seed |
| `make shell-api`, `make shell-db` | Abre shell no container ou psql |
| `make clean` | Remove containers + volumes |

Todos os comandos abaixo continuam válidos diretamente com `docker-compose`, mas recomenda-se usar os atalhos acima.

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

## 9. Troubleshooting

- **`ModuleNotFoundError: No module named 'app'` ao subir containers**: O `alembic/env.py` já injeta automaticamente o diretório `/app`
  no `PYTHONPATH`. Certifique-se de ter reconstruído a imagem (`make build` ou `docker compose build api`) após atualizar o repositório.
- **Aviso `the attribute version is obsolete` no `docker compose`**: O manifesto deixou de declarar `version`, portanto verifique se
  o `docker-compose.yml` local está atualizado antes de rodar `make dev`.
