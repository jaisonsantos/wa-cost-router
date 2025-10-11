[Docs](../current-cycle/README.md) › [Operações](./OPERATIONS.md)
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

## Circuit breaker de provedores

- Estados são persistidos em Redis (`circuit:{provider_id}`) e controlados por `CIRCUIT_BREAKER_THRESHOLD` (falhas consecutivas antes de abrir) e `CIRCUIT_BREAKER_COOLDOWN_SECONDS` (tempo mínimo até a transição para `half-open`).
- Quando um circuito está `open` ou `half-open`, o `RoutingEngine` ignora o provedor e utiliza a cadeia de fallback; logs incluem `event=circuit_breaker_skip` e métricas `messages_delivery_attempts_total{outcome="skipped_circuit"}`.
- Para simular em sandbox, aumente `SANDBOX_FAILURE_RATE` ou force respostas de erro no conector desejado. Após atingir o limiar, verifique `admin_circuit_breakers_open_total` e `messages_circuit_breaker_state{provider_id}` em `/admin/metrics`.
- Reset manual: `docker compose exec redis redis-cli DEL circuit:<provider_uuid>` (ou `FLUSHDB` para limpar todos). Fechamentos bem-sucedidos também ocorrem automaticamente quando o provedor processa uma mensagem com sucesso.
- Monitore gauges `admin_circuit_breakers_open_total` / `admin_circuit_breakers_half_open_total` e logs para planejar reativações ou ajustes de threshold.

## Rate limiting transacional

- Variáveis `RATE_LIMIT_MESSAGES_PER_MIN` e `RATE_LIMIT_LOGIN_PER_MIN` definem o número de chamadas permitidas por minuto e são exportadas automaticamente pelos targets do `Makefile` (valores padrão: 120 e 20 respectivamente).
- Ajuste temporariamente os limites para testes de carga ou demonstração (`RATE_LIMIT_MESSAGES_PER_MIN=2 make test-backend`).
- Eventos de estouro são registrados com `event=rate_limit_exceeded` nos logs da API, permitindo integração futura com Prometheus/Alertmanager.

## Segredos do webhook WhatsApp

- O secret usado para validar `X-Hub-Signature-256` fica armazenado criptografado em `wa_connection.webhook_secret_enc` (Fernet derivado de `APP_SECRET_KEY`).
- Para rotacionar, gere um novo secret no Meta Cloud API, atualize a conexão via `POST /integrations/wa/connections` (ou patch específico quando disponível) e aplique o mesmo valor na configuração do webhook Meta.
- Eventos assinados com o secret antigo passam a retornar `403`; monitore os logs estruturados (`message_event_ids`) para confirmar a adoção do novo valor.
- Nunca compartilhe o secret em texto claro; utilize os comandos administrativos para importar/exportar apenas através de variáveis de ambiente temporárias.

## Consentimento inbound e auditoria

- Cada mensagem inbound com campo `from` passa por verificação de opt-in (`contact_channel_opt_in`). Quando o consentimento está ausente, o webhook responde `{"status": "denied"}` e registra uma ocorrência em `contact_consent_audit` (`status=revoked`, `source="webhook"`, `proof_hash=sha256("denied:<provider_event_id>")`).
- As negações não criam `message_event` nem alteram métricas de tráfego. Consulte a tabela `contact_consent_audit` para auditar tentativas (filtre por `agent="wa_webhook"`).
- O serviço `OptInRequestService` é acionado para re-enfileirar solicitações de opt-in por e-mail. Verifique `contact_opt_in_request` para acompanhar follow-ups e reenvios.
- Para reprocessar um evento depois de concedido o consentimento, reenvie a notificação do Meta (o endpoint é idempotente por `provider_event_id`; remova o hash correspondente em `contact_consent_audit` se precisar liberar uma nova tentativa).

## Webhook SMS (Twilio)

- Endpoint `POST /integrations/sms/webhook` valida cada requisição com o header `X-Twilio-Signature` usando o `auth_token` armazenado nas credenciais do provedor (`provider_credential`). Requests sem assinatura ou com hash divergente retornam `403` para evitar spoofing.
- O mapeamento org/provedor é feito a partir do número destino (`To`) ou do `MessagingServiceSid` informado pelo Twilio. Os valores devem estar cadastrados no metadata/credenciais do provedor (`type = "sms"`), incluindo variações adicionais (`numbers`, `channels.sms.inbound_numbers`).
- Mensagens aceitas geram `message_event` com `channel="sms"`, normalizando telefone do contato e mascarando payload sensível (`Body`, `From`, `To`). O hash SHA-256 do corpo é persistido em `attributes.body_digest` para rastreabilidade sem expor conteúdo.
- Se o contato estiver cadastrado porém sem opt-in ativo, a requisição é negada (`{"status": "denied"}`) e o `OptInRequestService` enfileira follow-up por e-mail (`requested_channel="sms"`). Considere revisar cadastros e consentimentos após cada negação em produção.

## Pipeline CI

- **Workflow**: [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) executado em `push` e `pull_request` para `main`, além de gatilho manual via `workflow_dispatch`.
- **Ordem dos jobs**:
  1. `backend` — constrói as imagens Python, roda `alembic upgrade head` contra um Postgres efêmero e garante que o worker continue buildável.
  2. `frontend` — instala dependências com `npm ci`, roda `npm run lint` e `npm run build`, publicando o artefato `frontend-dist` com a pasta `dist/`.
  3. `e2e` — depende dos jobs anteriores, sobe a stack com Docker Compose, reaproveita os seeds demo e executa os testes Postman/Newman (ver [guia](../postman/README.md)). O relatório JUnit (`newman-report.xml`) é enviado como artefato para inspeção.
- **Depuração**: reexecute jobs individuais pelo GitHub (`Re-run failed jobs`) para validar correções rápidas. Para reproduzir localmente, utilize `make ci`, que encadeia `ci-backend`, `ci-frontend` e `ci-e2e` com os mesmos comandos do pipeline. Falhas no passo E2E geralmente aparecem no relatório Newman; baixe o artefato ou rode `make ci-e2e` para gerar um novo.
- **Limites de taxa no CI**: o workflow exporta `RATE_LIMIT_MESSAGES_PER_MIN=120` e `RATE_LIMIT_LOGIN_PER_MIN=20` garantindo que a suíte Newman opere dentro do teto padrão; ajuste via secrets caso ambientes gerenciados exijam limites distintos.
- **Referências**: detalhes de secrets, variáveis e troubleshooting ampliado em [CI avançado](./CI.md).

## Ordem de subida recomendada

1. Exporte variáveis sensíveis no `.env` da API (`backend/.env`).
2. Execute `make dev` e aguarde o tail de logs indicar `Application startup complete`.
3. Para reiniciar sem reseed, utilize `make down` seguido de `make dev`.
4. Em pipelines CI/CD, replicar a sequência: subir banco/cache → `alembic upgrade head` → seed opcional → iniciar API/worker.

## Saúde & observabilidade

- **Readiness**: `GET /admin/health` (proteção necessária antes de produção).
- **Workers**: monitorar filas Redis (`rq info`) e eventos de falha via logs.
- **Métricas Prometheus**: endpoint `/admin/metrics` publica contadores (`messages_send_total{status,provider,channel}`, `messages_delivery_attempts_total{provider_id,provider,outcome,channel}`, `admin_metrics_scrapes_total`, `sla_first_response_tracked_total{channel}`, `sla_first_response_within_target_total{channel}`), histograma (`sla_first_response_seconds{channel}`) e gauges (`messages_circuit_breaker_state{provider_id}`, `admin_circuit_breakers_open_total`, `admin_circuit_breakers_half_open_total`, `sla_first_response_target_seconds{channel}`). Mantenha protegido por rede privada ou auth (ver backlog P1 "proteger-admin-metrics").
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
- ✅ Limites de taxa revisados conforme necessidade (`RATE_LIMIT_MESSAGES_PER_MIN`, `RATE_LIMIT_LOGIN_PER_MIN`).
- ✅ `make migrate` executado na release candidata.
- ✅ `make postman-test` e smoke tests manuais (login, criar provider, enviar mensagem, consultar job).
- ✅ Monitoramento Prometheus + logs centralizados configurados.

## Veja também

- [Guia de migrations](./MIGRATIONS.md)
- [Guia de deploy](./DEPLOYMENT.md)
- [Backlog priorizado](../backlog/README.md)
