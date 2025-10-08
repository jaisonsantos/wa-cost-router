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

## Modo sandbox dos conectores

- `SANDBOX_PROVIDERS=true` (default em `.env.example`, `docker-compose.yml` e `make dev`) instrui a API/worker a usar `SandboxProviderConnector`, que não realiza chamadas HTTP externas.
- Ajuste `SANDBOX_LATENCY_MS` para simular latência média (padrão: 100 ms). Use `0` para execuções instantâneas no CI.
- `SANDBOX_FAILURE_RATE` aceita valores entre `0` e `1` para testar cenários de falha determinística; `0` garante que Newman termine sempre com sucesso.
- Ao desativar o sandbox (`false`), forneça credenciais reais de provedores e valide limites de taxa/billing antes de expor em produção.

## Segredos do webhook WhatsApp

- O secret usado para validar `X-Hub-Signature-256` fica armazenado criptografado em `wa_connection.webhook_secret_enc` (Fernet derivado de `APP_SECRET_KEY`).
- Para rotacionar, gere um novo secret no Meta Cloud API, atualize a conexão via `POST /integrations/wa/connections` (ou patch específico quando disponível) e aplique o mesmo valor na configuração do webhook Meta.
- Eventos assinados com o secret antigo passam a retornar `403`; monitore os logs estruturados (`message_event_ids`) para confirmar a adoção do novo valor.
- Nunca compartilhe o secret em texto claro; utilize os comandos administrativos para importar/exportar apenas através de variáveis de ambiente temporárias.

## Pipeline CI

- **Workflow**: [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) executado em `push` e `pull_request` para `main`, além de gatilho manual via `workflow_dispatch`.
- **Ordem dos jobs**:
  1. `backend` — constrói as imagens Python, roda `alembic upgrade head` contra um Postgres efêmero e garante que o worker continue buildável.
  2. `frontend` — instala dependências com `npm ci`, roda `npm run lint` e `npm run build`, publicando o artefato `frontend-dist` com a pasta `dist/`.
  3. `e2e` — depende dos jobs anteriores, sobe a stack com Docker Compose, reaproveita os seeds demo e executa os testes Postman/Newman (ver [guia](../postman/README.md)). O relatório JUnit (`newman-report.xml`) é enviado como artefato para inspeção.
- **Depuração**: reexecute jobs individuais pelo GitHub (`Re-run failed jobs`) para validar correções rápidas. Para reproduzir localmente, utilize `make ci`, que encadeia `ci-backend`, `ci-frontend` e `ci-e2e` com os mesmos comandos do pipeline. Falhas no passo E2E geralmente aparecem no relatório Newman; baixe o artefato ou rode `make ci-e2e` para gerar um novo.
- **Referências**: detalhes de secrets, variáveis e troubleshooting ampliado em [CI avançado](./CI.md).

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
