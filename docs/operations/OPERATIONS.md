[Docs](../overview/README.md) › [Operações](./OPERATIONS.md)
# Operações & Runbooks

Este guia cobre tarefas rotineiras para operar o WA Cost Router em ambientes de desenvolvimento, homologação e produção.

## Fluxos principais

| Fluxo | Comando | Observações |
|-------|---------|-------------|
| Provisionar ambiente local | `make dev` | Sobe `db`/`redis`, aplica migrations, roda seed idempotente e inicia `api`, `web`, `worker`, finalizando com `logs -f api`. |
| Atualizar schema | `make migrate` | Executa `alembic upgrade head` sem subir serviços. Sempre rodar antes de novas releases. |
| Popular dados demo | `make seed` | Apenas insere dados de exemplo (org, usuário, rates, eventos). Não cria tabelas. |
| Executar coleção Postman | `make postman-test` | Usa `npx newman` com coleção/ambiente em `docs/postman/`. |
| Derrubar stack | `make down` | Remove containers **e volumes** para reset rápido. |

Os comandos herdados de `docker-compose` continuam válidos, mas os alvos do Makefile padronizam a ordem correta (migrations → seed → serviços).

## Ordem de subida recomendada

1. Exporte variáveis sensíveis no `.env` da API (`backend/.env`).
2. Execute `make dev` e aguarde o tail de logs indicar `Application startup complete`.
3. Para reiniciar sem reseed, utilize `make down` seguido de `make dev`.
4. Em pipelines CI/CD, replicar a sequência: subir banco/cache → `alembic upgrade head` → seed opcional → iniciar API/worker.

## Saúde & observabilidade

- **Readiness**: `GET /admin/health` (proteção necessária antes de produção).
- **Workers**: monitorar filas Redis (`rq info`) e eventos de falha via logs.
- **Métricas Prometheus**: endpoint `/admin/metrics`. Mantenha protegido por rede privada ou auth (ver backlog P1 "proteger-admin-metrics").
- **Logs**: `make logs` segue a API com `--tail=200`. Para outros serviços use `docker-compose logs -f <service>`.

## Backup & restore

- **Postgres**: `pg_dump wa_cost_router > backup.sql` dentro do container `db`.
- **Restore**: `psql -d wa_cost_router < backup.sql`.
- Automatizar snapshots diários e testar restore em ambiente isolado.

## Troubleshooting

| Sintoma | Ação |
|---------|------|
| `sqlalchemy.exc.InvalidRequestError: Attribute name 'metadata' is reserved` | Confirme que migrations estão atualizadas (build atual usa coluna `meta = Column("metadata")`). Rode `make migrate`. |
| Seeds falham com constraint unique | O script é idempotente. Verifique se dados foram corrompidos; execute `make seed` novamente após `make migrate`. |
| API não sobe após `make dev` | Veja logs da API. Normalmente indica migrations pendentes ou secrets ausentes (`APP_SECRET_KEY`, `JWT_SECRET`). |
| `alembic command not found` | Confirme que está executando via `make`/`docker-compose run --rm api ...` para usar a imagem com deps. |

## Checklist pré-deploy

- ✅ Variáveis sensíveis definidas (`APP_SECRET_KEY`, `JWT_SECRET`, `DATABASE_URL`, `REDIS_URL`).
- ✅ `make migrate` executado na release candidata.
- ✅ `make postman-test` e smoke tests manuais (login, criar provider, enviar mensagem, consultar job).
- ✅ Monitoramento Prometheus + logs centralizados configurados.

## Veja também

- [Guia de migrations](./MIGRATIONS.md)
- [Guia de deploy](./DEPLOYMENT.md)
- [Backlog priorizado](../backlog/README.md)
