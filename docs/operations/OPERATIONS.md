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

## Configuração de CORS da API

- Defina `API_CORS_ORIGINS` com uma lista separada por vírgulas (`https://app.example.com,https://admin.example.com`) para autorizar chamadas do frontend.
- Se o valor ficar em branco e o ambiente for `ENVIRONMENT=local|dev|test`, a API libera apenas os hosts de desenvolvimento padrão (`http://localhost/127.0.0.1` nas portas 5173 e 8080`).
- Em ambientes de homologação/produção sempre declare explicitamente os domínios confiáveis; um valor vazio bloqueia origens externas.

## Secrets obrigatórios por ambiente

- `Settings` bloqueia a inicialização caso `JWT_SECRET` ou `APP_SECRET_KEY` permaneçam com os valores padrão quando `ENVIRONMENT` estiver configurado para `staging`, `qa`, `production` (ou qualquer outro fora de `local|dev|test`).
- Gere secrets fortes com `openssl rand -base64 32` e injete-os via variáveis de ambiente/secret manager do orquestrador.
- Atualize o checklist pré-deploy para garantir que os secrets rotacionados estão registrados e acessíveis para a API e workers.

## Envio assíncrono de mensagens

- `POST /messages/send` responde `202 Accepted` com o `job_id` e registra o job como `pending`; o processamento é realizado pelo worker RQ na fila `message_send`.
- Em ambientes `ENVIRONMENT=local|dev|test` os horários de silêncio de marketing (`MARKETING_SILENT_HOURS_UTC`) são desativados automaticamente para evitar retornos 403 acidentais em demos e na suíte Newman. Defina explicitamente a variável para restaurar a janela em homologação/produção.
- Templates WhatsApp sincronizados carregam metadados normalizados (`blocked_countries`, `allowed_hours`, etc. – sempre em maiúsculas, faixas `HH:MM-HH:MM` e sem duplicidades). As regras são reavaliadas a cada envio; se o provedor remover as restrições, o `meta` local é limpo na próxima sincronização. Violações retornam `403` com `detail.code = template_*` e o job é marcado como `failed_final` para auditoria.
- O worker dedicado (vide `backend/app/workers/message_send.py`) executa `MessageDeliveryService`, atualizando `MessageJob`, `DeliveryAttempt`, `MessageEvent` e métricas (`messages_send_total`, `messages_delivery_attempts_total`, `messages_circuit_breaker_state`).
- Para acompanhar a fila utilize `docker compose exec redis rq info message_send` ou `rq worker message_send` em ambientes que utilizem workers separados.
- Idempotência permanece garantida por `(org_id, idempotency_key)`. Requisições repetidas retornam `200 OK` com o status consolidado do job.
- Em incidentes, verifique o log do worker (`make logs worker`) e confirme o estado no banco (`SELECT status FROM message_job WHERE id = '<job_id>'`).

## Modo sandbox dos conectores

- `SANDBOX_PROVIDERS=true` (default em `.env.example`, `docker-compose.yml` e `make dev`) instrui a API/worker a usar `SandboxProviderConnector`, que não realiza chamadas HTTP externas.
- Ajuste `SANDBOX_LATENCY_MS` para simular latência média (padrão: 100 ms). Use `0` para execuções instantâneas no CI.
- `SANDBOX_FAILURE_RATE` aceita valores entre `0` e `1` para testar cenários de falha determinística; `0` garante que Newman termine sempre com sucesso.
- Ao desativar o sandbox (`false`), forneça credenciais reais de provedores e valide limites de taxa/billing antes de expor em produção.

### Configuração dinâmica de provedores

- **Twilio (SMS)**
  - Preencha `account_sid`, `auth_token`, `from_number` (E.164) e `inbound_verify_token` na UI. Os campos são validados conforme o schema retornado pelo backend.
  - Documente campanhas 10DLC e mantenha evidências de opt-in por destinatário. Sem registro, o tráfego pode ser bloqueado pelos carriers.
  - Após salvar, execute o botão "Testar" na UI ou `POST /providers/{id}/health` para confirmar `healthy=true`. Em sandbox o número padrão é `+15558675309` e o token de webhook deve coincidir com `sms_webhook_auth_token`.
- **SendGrid (Email)**
  - Informe `api_key`, `from_email`, `webhook_token` e `inbound_signing_secret`. O schema valida o formato da API key (`SG.*`) e do remetente.
  - Garanta que SPF e DKIM estejam ativos no domínio antes de enviar em produção e respeite listas de supressão (`unsubscribe`).
  - Health check (`POST /integrations/email/test` ou botão na UI) usa o segredo para validar a assinatura do Event Webhook; execute sempre após atualizar credenciais.
- **360dialog / Gupshup (WhatsApp)** continuam aceitando `access_token` (360dialog) ou `api_key`/`app_name` (Gupshup), agora descritos no schema retornado por `GET /providers`.

### Monitoramento de conexões

- `GET /integrations/connections` expõe o estado agregado por canal (`status`, `connected`, `has_credentials`, `last_health_check`). Utilize-o para verificar rapidamente se a organização possui credenciais válidas antes de iniciar testes ou demonstrações.
- Estados possíveis: `healthy` (último health check bem-sucedido), `warning` (conectado mas com códigos ≠2xx), `error` (falha ou exceção), `disconnected` (sem credenciais ativas), `unknown` (nunca testado).
- `POST /integrations/{channel}/test` executa o health check no ato usando o conector apropriado (`whatsapp`, `email`, `sms`). Para canais com múltiplos provedores informe `provider_id` no corpo.
- Resultados são persistidos em `integration_health_status` e reaproveitados pelo endpoint de listagem. Em caso de erro, o campo `error` traz a mensagem retornada pelo conector (ex.: `Unauthorized`, `Timeout`).
- Rotina recomendada no plantão: consultar `/integrations/connections` após cada deploy e executar `POST /integrations/{channel}/test` quando houver alerta `warning`/`error`, registrando ações no playbook de incidentes.
- Cenários automatizados: `tests/e2e/settings-connections.spec.ts` usa o sandbox para validar tanto o fluxo saudável quanto uma simulação de falha (badge "Falha") pressionando os botões "Testar Email/SMS" na UI.

## Billing & Stripe

- Defina `STRIPE_SECRET_KEY` e `STRIPE_WEBHOOK_SECRET` no `.env` do backend antes de habilitar o checkout. Sem esses valores a API responde `503` ao iniciar um fluxo de assinatura.
- `POST /billing/checkout` cria uma sessão de assinatura no Stripe com Stripe Tax habilitado (`automatic_tax`). Informe `price_id`, `success_url` e `cancel_url`. O backend garante idempotência por `org_id` reaproveitando o `customer` existente e pré-cria o registro em `billing_invoice`.
- `POST /billing/portal` abre o Stripe Customer Portal com `automatic_tax` forçado para `true`, permitindo que o cliente ajuste plano/pagamento mantendo o cálculo fiscal automático.
- `POST /billing/webhook` processa eventos `checkout.session.completed`, `customer.subscription.updated/deleted` e `invoice.paid`. O payload precisa carregar `metadata.org_id` para vincular a organização e atualiza `billing_invoice.tax_amount_total_minor`, `billing_subscription.tax_amount_total_minor` e links de invoice.
- `GET /billing/summary` expõe o plano atual, limites de mensagens e status de pagamento. A aba *Billing* em `Settings` consome esse endpoint para exibir preço, próxima fatura e método de pagamento mascarado.
- Worker `billing_usage` continua responsável pelos UsageRecords; o novo worker `billing_reconcile` (fila `billing_reconcile`) compara invoices locais × Stripe diariamente, emitindo logs `event=billing_reconcile_item` e populando a métrica `billing_reconcile_drift{org_id}`.
- Para testes locais use os fixtures do Stripe (`backend/tests/test_billing_api.py`, `backend/tests/test_billing_tax.py`) ou sobrescreva `verify_webhook_event` via monkeypatch. As assinaturas simuladas atualizam as tabelas `billing_subscription` e `billing_invoice` sem necessidade de chamadas externas.

## Circuit breaker de provedores

- Estados são persistidos em Redis (`circuit:{provider_id}`) e controlados por `CIRCUIT_BREAKER_THRESHOLD` (falhas consecutivas antes de abrir) e `CIRCUIT_BREAKER_COOLDOWN_SECONDS` (tempo mínimo até a transição para `half-open`).
- Quando um circuito está `open` ou `half-open`, o `RoutingEngine` ignora o provedor e utiliza a cadeia de fallback; logs incluem `event=circuit_breaker_skip` e métricas `messages_delivery_attempts_total{outcome="skipped_circuit"}`.
- Para simular em sandbox, aumente `SANDBOX_FAILURE_RATE` ou force respostas de erro no conector desejado. Após atingir o limiar, verifique `admin_circuit_breakers_open_total` e `messages_circuit_breaker_state{provider_id}` em `/admin/metrics` enviando o header `X-Admin-Token`.
- Reset manual: `docker compose exec redis redis-cli DEL circuit:<provider_uuid>` (ou `FLUSHDB` para limpar todos). Fechamentos bem-sucedidos também ocorrem automaticamente quando o provedor processa uma mensagem com sucesso.
- Monitore gauges `admin_circuit_breakers_open_total` / `admin_circuit_breakers_half_open_total` e logs para planejar reativações ou ajustes de threshold.

## Rate limiting transacional

- Variáveis `RATE_LIMIT_MESSAGES_PER_MIN` e `RATE_LIMIT_LOGIN_PER_MIN` definem o número de chamadas permitidas por minuto e são exportadas automaticamente pelos targets do `Makefile` (valores padrão: 120 e 20 respectivamente).
- Ajuste temporariamente os limites para testes de carga ou demonstração (`RATE_LIMIT_MESSAGES_PER_MIN=2 make test-backend`).
- Eventos de estouro são registrados com `event=rate_limit_exceeded` nos logs da API, permitindo integração futura com Prometheus/Alertmanager.

## Monitoramento de SLA multicanal

- `ConversationLifecycleService` atualiza as filas em `queue_entry` sempre que um webhook inbound cria/encerra conversas. Use `GET /reports/queues` para acompanhar backlog e tempo médio de primeira resposta por canal.
- `GET /reports/channel-metrics` fornece a mesma visão agregada, incluindo `sla.target_seconds` e `sla.compliance_rate` alinhados ao Prometheus (`sla_first_response_*`).
- Para recalcular snapshots em lote, execute no container da API:

  ```bash
  docker compose exec api python -c "from app.services.conversations.worker import enqueue_sla_snapshot_rebuild; enqueue_sla_snapshot_rebuild(org_id='${ORG_ID}', sla_target_seconds=60)"
  ```

  Isso agenda a tarefa no worker RQ. Para forçar a execução síncrona (debug), use `docker compose exec api python -c "from app.services.conversations.worker import rebuild_sla_snapshots; rebuild_sla_snapshots(org_id='${ORG_ID}', sla_target_seconds=60)"`.
- Dashboards externos podem coletar os indicadores diretamente do Prometheus exportado em `/admin/metrics` (`sla_first_response_seconds`, `sla_first_response_within_target_total`, `messages_delivery_attempts_total{channel=...}`) desde que enviem o header `X-Admin-Token` com o token configurado.
- Configure alertas de SLA acompanhando a razão `sla_first_response_within_target_total / sla_first_response_tracked_total` nos canais críticos (`whatsapp`, `sms`).

## Segredos do webhook WhatsApp

- O secret usado para validar `X-Hub-Signature-256` fica armazenado criptografado em `wa_connection.webhook_secret_enc` (Fernet derivado de `APP_SECRET_KEY`).
- Para rotacionar, gere um novo secret no Meta Cloud API, atualize a conexão via `POST /integrations/wa/connections` (ou patch específico quando disponível) e aplique o mesmo valor na configuração do webhook Meta.
- Eventos assinados com o secret antigo passam a retornar `403`; monitore os logs estruturados (`message_event_ids`) para confirmar a adoção do novo valor.
- Nunca compartilhe o secret em texto claro; utilize os comandos administrativos para importar/exportar apenas através de variáveis de ambiente temporárias.

## Consentimento inbound e auditoria

- `MultiChannelConsentResolver` consulta `contact_channel_opt_in` e preferências derivadas antes de aceitar webhooks (`whatsapp`, `sms`). Sem consentimento ativo o retorno é `{ "status": "denied" }` e uma ocorrência é gravada em `contact_consent_audit` (`status=revoked`, `source="webhook"`, `proof_hash=sha256("denied:<provider_event_id>")`).
- As negações não criam `message_event` nem alteram métricas de tráfego. Consulte a tabela `contact_consent_audit` para auditar tentativas (filtre por `agent` = `wa_webhook` ou `sms_webhook`).
- O serviço `OptInRequestService` é acionado para re-enfileirar solicitações de opt-in por e-mail/SMS. Verifique `contact_opt_in_request` para acompanhar follow-ups, data de expiração e resultado do reenvio.
- Para reprocessar um evento depois de concedido o consentimento, reenvie a notificação do provedor. Os endpoints são idempotentes por `provider_event_id`/`MessageSid`; se necessário exclua o hash correspondente em `contact_consent_audit` para liberar a nova tentativa.

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
- **Falhas por billing**: se o GitHub Actions exibir `The job was not started because recent account payments have failed or your spending limit needs to be increased`, nenhum job é executado — trata-se de bloqueio administrativo do GitHub. Siga o [runbook de desbloqueio](../runbooks/ci_billing.md) para regularizar pagamentos, confirmar o status **All workflows enabled** e só então reexecutar o workflow.
- **Plano de recuperação**: quando o bloqueio impactar múltiplos PRs, siga o [plano de correção](./CI_RECOVERY_PLAN.md) para coordenar diagnóstico, mitigação (`make ci-lite`), regularização financeira e comunicação com stakeholders.
- **Validação manual temporária**: enquanto o Actions estiver bloqueado, rode `make ci-lite` para executar lint/build/pytest sem Docker e gere `artifacts/ci-lite/summary.json`. Anexe o relatório ao PR e, quando necessário, complemente com `make postman-test`.
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
- **Métricas Prometheus**: endpoint `/admin/metrics` publica contadores (`messages_send_total{status,provider,channel}`, `messages_delivery_attempts_total{provider_id,provider,outcome,channel}`, `admin_metrics_scrapes_total`, `sla_first_response_tracked_total{channel}`, `sla_first_response_within_target_total{channel}`), histograma (`sla_first_response_seconds{channel}`) e gauges (`messages_circuit_breaker_state{provider_id}`, `admin_circuit_breakers_open_total`, `admin_circuit_breakers_half_open_total`, `sla_first_response_target_seconds{channel}`). Mantenha protegido por rede privada e envie `X-Admin-Token` com o valor de `METRICS_AUTH_TOKEN` (ou fallback local).
- **Logs**: `make logs` segue a API com `--tail=200`. Para outros serviços use `docker-compose logs -f <service>`.

### Autenticação de `/admin/metrics`

- Defina `METRICS_AUTH_TOKEN` com um segredo forte em ambientes `ENVIRONMENT=staging|production`. O header padrão esperado é `X-Admin-Token` (`METRICS_AUTH_HEADER_NAME`).
- Em `ENVIRONMENT=local`/`test`, o backend usa `METRICS_AUTH_LOCAL_TOKEN` como fallback para evitar bloqueios em desenvolvimento.
- Atualize os scrapers Prometheus (ou clientes HTTP) para enviar o header configurado. Exemplo:

  ```yaml
  - job_name: wa-cost-router
    scheme: https
    metrics_path: /admin/metrics
    authorization:
      type: Bearer
      credentials: ${WA_COST_ROUTER_METRICS_TOKEN}
    headers:
      X-Admin-Token: ${WA_COST_ROUTER_METRICS_TOKEN}
  ```

- Gere tokens distintos por ambiente e rotacione via secrets manager. Falhas de autenticação retornam `401` (ausente) ou `403` (inválido) e são logadas com `event=admin_metrics_auth_missing`/`admin_metrics_scrape`.

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
