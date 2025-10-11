[Docs](../current-cycle/README.md) › [Postman](./README.md)
# Coleção Postman

A coleção `WA Cost Router` cobre 100% dos endpoints do backend com variáveis encadeadas para um fluxo E2E completo.

> ℹ️ A stack local (`make dev`/`make ci`) roda com `SANDBOX_PROVIDERS=true`, portanto os requests de Providers/Messages executam em memória sem atingir provedores externos. Ajuste `SANDBOX_LATENCY_MS` e `SANDBOX_FAILURE_RATE` para simular cenários diferentes quando necessário.

## Estrutura

1. **Auth** – registra usuário aleatório (`postman+timestamp`) com senha forte gerada no runtime e efetua login (token salvo automaticamente).
2. **Organization** – obtém `org_id` via `/orgs/current`.
3. **Providers** – cria provedor WhatsApp (360dialog), salva credenciais fake e executa health check.
4. **Rules** – lista, cria, atualiza e alterna regras, incluindo simulação avançada.
5. **Messages** – envia mensagem, lista jobs, consulta detalhes do job usando `job_id` capturado, executa o cenário opcional **Messages - Rate Limit Demo** para validar respostas `429` e concentra a pasta **Multi-Channel Regression** para validar WhatsApp/SMS/e-mail.
6. **Contacts** – dispara importação assíncrona (`POST /contacts/imports`), lista catálogos, cria contato, edita atributos, alterna status ativo/inativo e consulta histórico de consentimento.
7. **Contact Segments** – cria segmento, atualiza metadados, associa/desassocia o contato criado e configura política de limites/opt-out.
8. **Rates** – consulta tarifas e importa CSV de exemplo (`docs/postman/sample_rates.csv`) usando o `provider_name` do provedor criado na etapa Providers.
9. **Reports** – consome métricas de dashboard, resumo, métricas por provedor e valida que `/events` retorna `unit_cost_minor`/`baseline_cost_minor`.
10. **Integrations** – cria conexão WA, valida webhook (`hub.verify_token`) e envia payload de webhook (repetir a criação com o mesmo `phone_id` apenas atualiza o registro).
11. **Admin** – checa `/admin/health` e `/admin/metrics`.
12. **Cleanup** – remove credenciais do provedor criado durante o fluxo.

Scripts de coleção adicionam o header `Authorization` automaticamente sempre que `token` estiver definido e validam que todas as respostas retornem status 2xx.

## Variáveis de ambiente

Arquivo: [`wa-cost-router.postman_environment.json`](./wa-cost-router.postman_environment.json)

| Variável | Descrição |
|----------|-----------|
| `base_url` | URL base da API (default `http://localhost:8000`). |
| `email` / `password` | Credenciais seed (`admin@demo.local` / `demo123`) usadas como fallback até o prerequest gerar valores fortes por execução. |
| `token` | JWT salvo pelos testes (não preencha manualmente). |
| `org_id`, `provider_id`, `rule_id`, `job_id`, `contact_id`, `segment_id`, `contact_import_job_id` | IDs capturados automaticamente para uso em chamadas subsequentes. |
| `rates_csv_path` | Caminho do CSV usado no import de tarifas (`docs/postman/sample_rates.csv`). |
| `contacts_csv_path` | Caminho do CSV usado no import de contatos (`docs/postman/sample_contacts.csv`). |
| `rate_limit_demo_enabled` | Quando `true`, o request **Messages - Rate Limit Demo** dispara chamadas adicionais para demonstrar `429` (requer ajustar os limites da API para valores baixos). |
| `wa_phone_id`, `wa_business_id`, `wa_access_token`, `wa_verify_token`, `wa_webhook_secret` | Dados seed para testar integrações WhatsApp (incluindo secret usado no HMAC do webhook). |
| `wa_contact_phone` | Número E.164 usado como remetente no payload do webhook; ajuste conforme o contato criado no catálogo. |
| `sms_contact_phone` | Número E.164 usado como originador das mensagens SMS (reaproveitado nos testes multi-canal). |
| `sms_inbound_number` | Número curto/long code configurado como destino nos webhooks SMS. |
| `sms_messaging_service_sid` | SID opcional do Messaging Service (Twilio) para validar roteamento inbound. |
| `sms_webhook_auth_token` | Token de autenticação (Twilio Auth Token) utilizado para assinar o webhook SMS. |
| `email_webhook_token` | Token utilizado para autenticar as rotas `/integrations/email/webhook`. |
| `email_webhook_secret` | Secret usado para assinar o header `X-Email-Signature` nas requisições inbound de e-mail. |

### Assinatura do webhook

#### WhatsApp

- `WA - Webhook Receive` calcula automaticamente o header `X-Hub-Signature-256` em um script *pre-request* usando HMAC SHA-256 do corpo bruto com a variável `wa_webhook_secret` (`sha256=<hex>`).
- Execute **WA - Create Connection** antes das requisições para garantir que a API esteja usando o mesmo secret; quando o header de assinatura não for enviado, os eventos serão ignorados com `status: ignored`.
- O payload de exemplo inclui `metadata.phone_number_id` e deve combinar com `wa_phone_id` para que o evento seja aceito. Use `wa_contact_phone` para simular o número do contato: se o catálogo não possuir opt-in ativo para esse número, a resposta será `{ "status": "denied" }` e o payload do evento é mascarado automaticamente nos registros.

#### SMS (Twilio)

- `SMS - Webhook Receive` envia corpo `x-www-form-urlencoded` com os campos padrão (`MessageSid`, `MessagingServiceSid`, `From`, `To`, `Body`, `Timestamp`).
- O script *pre-request* ordena os pares chave/valor, concatena com a URL final (`{{base_url}}/integrations/sms/webhook`) e calcula o HMAC SHA-1 usando `sms_webhook_auth_token`, reproduzindo a assinatura da Twilio. O digest é convertido em Base64 e enviado no header `X-Twilio-Signature`.
- Ajuste `sms_contact_phone`, `sms_inbound_number` e, quando aplicável, `sms_messaging_service_sid` para simular múltiplos números inbound por organização.

#### E-mail

- `Email - Webhook Verify` utiliza `email_webhook_token` para responder o desafio (`challenge`) enviado pelo provedor.
- `Email - Webhook Receive` espera o mesmo token na query string (`token=...`) e assina o corpo JSON com HMAC SHA-256 usando `email_webhook_secret`, serializado em Base64 para o header `X-Email-Signature`.
- O payload de exemplo aceita arrays (lista de eventos SendGrid) ou objetos únicos; quando `email_webhook_secret` estiver vazio, a assinatura é enviada como string vazia para facilitar depuração.

## Fluxo recomendado

1. **Auth - Register** → **Auth - Login** (token e email são persistidos).
2. **Organization - Current** para preencher `org_id`.
3. Rodar sequência em **Providers** (Create → Save Credentials → Health Check).
4. Executar pasta **Rules** inteira (toggle final reativa a regra).
5. **Messages** (Send → Jobs → Job Detail; a pasta **Multi-Channel Regression** roda automaticamente via `make postman-test`).
6. **Contacts** (Import CSV → List → Create → Update → Opt-Out → Opt-In → Consent History) utilizando os IDs armazenados automaticamente.
7. **Contact Segments** (Create → List → Update → Add Contacts → Remove Contact → Upsert Policy → Delete) para validar o fluxo de segmentação.
8. **Rates**, **Reports** e **Integrations**.
9. Concluir com **Admin** e **Cleanup**.

Todos os requests foram configurados para funcionar em sequência via Newman, usando dados `seed` fornecidos por `make dev`.

### Demonstração de rate limit (`429 Too Many Requests`)

1. Ajuste os limites do backend exportando, no terminal, valores pequenos (ex.: `RATE_LIMIT_MESSAGES_PER_MIN=2 RATE_LIMIT_LOGIN_PER_MIN=2 make dev`).
2. No Postman, altere a variável de ambiente `rate_limit_demo_enabled` para `true`.
3. Execute **Messages - Rate Limit Demo**: a primeira chamada confirma o header `X-RateLimit-Remaining`; as chamadas subsequentes feitas via script retornam `429` com `Retry-After` e `X-RateLimit-Remaining: 0`.
4. Restaure os limites padrão removendo as variáveis ou definindo valores maiores antes de repetir o fluxo normal de mensagens.

### Demonstração de circuit breaker (rota com fallback)

1. Suba a API exportando valores baixos para abrir o circuito rapidamente: `CIRCUIT_BREAKER_THRESHOLD=1 SANDBOX_FAILURE_RATE=1 make dev`.
2. No Postman, execute **Messages - Send** duas vezes com o mesmo `channel_address` (WhatsApp). A primeira chamada falhará no provedor principal; a segunda utilizará o fallback imediatamente.
3. Consulte **Admin - Metrics** ou rode `docker compose exec redis redis-cli GET circuit:<provider_uuid>` para confirmar `state":"open"` e verifique os gauges `admin_circuit_breakers_open_total` / `messages_circuit_breaker_state{provider_id}`.
4. Restaure `SANDBOX_FAILURE_RATE=0` e realize novo envio para fechar o circuito (estado volta para `closed`).

## Executando testes automatizados

```bash
make postman-test
```

O comando executa dois runs via `npx newman`: o fluxo completo da coleção e, em seguida, a pasta **Multi-Channel Regression** parametrizada pelo arquivo [`docs/postman/multi_channel_regression.json`](./multi_channel_regression.json). Certifique-se de que a API esteja rodando (`make dev`) antes de executar.

### Regressão multi-canal

O arquivo [`multi_channel_regression.json`](./multi_channel_regression.json) parametriza o request **Messages - Send (Multi-Channel)** com canais distintos:

- `channel`: aceita `whatsapp`, `sms` ou `email` (pode ser expandido para novos canais sem alterar a coleção).
- `address_env`: nome da variável de ambiente que contém o endereço do canal (quando vazio, o script gera fallback). Para e-mail é gerado automaticamente `postman-multichannel-<timestamp>@example.com`.
- `variables`: objeto arbitrário enviado para o template — utilize chaves coerentes com os placeholders cadastrados no backend.

Ao rodar `make postman-test`, todos os cenários são processados sequencialmente e o `job_id` da última execução permanece disponível para consultas posteriores.

## Veja também

- [Referência da API](../api/API_REFERENCE.md)
- [Guia de operações](../operations/OPERATIONS.md)
- [Backlog priorizado](../backlog/README.md)
