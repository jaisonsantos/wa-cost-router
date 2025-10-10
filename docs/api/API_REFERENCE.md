[Docs](../current-cycle/README.md) › [API](./API_REFERENCE.md)
# Referência da API

Todas as rotas utilizam JSON e, salvo indicação contrária, exigem o header `Authorization: Bearer <token>`. Os exemplos assumem o ambiente local (`http://localhost:8000`) e estão sincronizados com a coleção Postman em `docs/postman/wa-cost-router.postman_collection.json`.

## Convenções gerais

- Erros de validação Pydantic/FastAPI retornam `422 Unprocessable Entity` com detalhes em `detail[].msg`.
- Identificadores seguem o formato UUID v4.
- Datas são serializadas em ISO 8601 com timezone UTC (`2025-10-09T11:30:00+00:00`).
- O Postman injeta automaticamente o token JWT ativo nas requisições por meio de script de pré-requisição.

## Autenticação

### `POST /auth/register`

Cria um usuário, a primeira organização e retorna um token JWT.

| Campo            | Tipo   | Obrigatório | Observações |
|------------------|--------|-------------|-------------|
| `email`          | string | sim         | Aceita domínios `.local`; normalizado para minúsculas. |
| `password`       | string | sim         | Armazenado com hash bcrypt. |
| `org_name`       | string | sim         | Nome da organização inicial. |

**Respostas**
- `200 OK` – `{"access_token": "<jwt>", "token_type": "bearer"}`.
- `400 Bad Request` – `"Email already registered"` quando o e-mail existe.

### `POST /auth/login`

Gera um token para usuário existente vinculado a uma organização.

| Campo      | Tipo   | Obrigatório | Observações |
|------------|--------|-------------|-------------|
| `email`    | string | sim         | Normalizado via `_normalize_email`. |
| `password` | string | sim         | Comparado com o hash persistido. |

**Respostas**
- `200 OK` – `TokenResponse` idêntica a `/auth/register`.
- `401 Unauthorized` – credenciais inválidas.
- `400 Bad Request` – usuário sem vínculo organizacional.
- `429 Too Many Requests` – limite por organização excedido; headers `Retry-After` (segundos para novo slot) e `X-RateLimit-Remaining` (sempre `0`).

## Organização

### `GET /orgs/current`
Retorna metadados da organização ativa do token.

**Resposta 200**
```json
{
  "id": "<org_id>",
  "name": "Demo Org",
  "user_email": "user@example.com",
  "role": "owner"
}
```
Erros: `404 Not Found` se a organização não existir (token inválido ou órfão).

## Contatos

### `GET /contacts`
Lista contatos da organização autenticada com paginação (`limit`, `offset`) e filtros opcionais.

| Query param | Tipo | Descrição |
| --- | --- | --- |
| `status` | enum `active\|inactive\|archived` | Filtra por status de ciclo de vida. |
| `channel` | string | Restringe opt-ins carregados (`whatsapp`, `sms`, `email`, etc.). |
| `opt_in_status` | array enum `granted\|pending\|revoked` | Retorna apenas contatos com opt-ins nos status indicados. |
| `segment_id` | array UUID | Filtra por segmentos (IDs). |
| `segment_slug` | array string | Filtra por segmentos (slugs). |
| `channel_address` | string | Exige opt-in para o endereço informado (telefone/e-mail normalizado). |

**Resposta 200**
```json
{
  "items": [
    {
      "id": "<uuid>",
      "org_id": "<uuid>",
      "full_name": "Maria Example",
      "email": "maria@example.com",
      "phone": "+5511999999999",
      "status": "active",
      "source": "import",
      "created_at": "2025-10-08T12:00:00+00:00",
      "updated_at": "2025-10-08T12:10:00+00:00"
    }
  ],
  "limit": 25,
  "offset": 0,
  "count": 1
}
```

### `POST /contacts`
Cria um contato. Campos aceitos: `external_id`, `full_name`, `first_name`, `last_name`, `email`, `phone`, `status`, `attributes`, `source`, `source_metadata`.

**Resposta 201** – objeto `ContactResponse` completo. Erros: `400` (violação de unicidade ou payload inválido), `422` (erros de validação), `409` (duplicado pela combinação `org_id` + `external_id`).

### `PATCH /contacts/{id}`
Atualiza campos específicos do contato. Responde `404` para IDs inexistentes. Mesmos campos do `POST`, todos opcionais.

### `DELETE /contacts/{id}`
Remove o contato e associações (`204 No Content`). Responde `404` quando o recurso não pertence à organização.

### `GET /contacts/{id}/consents/history`
Retorna auditoria completa de opt-ins.

**Resposta 200**
```json
{
  "items": [
    {
      "id": "<uuid>",
      "opt_in_id": "<uuid>",
      "opt_in_version": 2,
      "channel": "whatsapp",
      "channel_address": "+5511999999999",
      "status": "granted",
      "agent": "privacy-ops",
      "source": "manual",
      "recorded_at": "2025-10-08T12:02:00+00:00",
      "evidence_uri": "https://s3.internal/optins/123.pdf"
    }
  ],
  "count": 1
}
```

### `POST /contacts/imports`
Importa CSV. Payload `multipart/form-data` com campo `upload` (arquivo). Responde `202 Accepted` com resumo do job:

```json
{
  "id": "<job_id>",
  "status": "pending",
  "input_uri": "s3://wa-cost-router-imports/demo/2025-10-08.csv",
  "total_rows": 0,
  "processed_rows": 0,
  "error_rows": 0
}
```

Jobs finalizados expõem `processed_rows`, `error_rows` e `error_report_uri`. Consulte `/contacts/imports/{job_id}` para status. Erros: `400` (arquivo inválido) e `500` (falha ao agendar job).

## Provedores

### `GET /providers`
Lista provedores disponíveis para a organização autenticada.

**Resposta 200** – array de objetos `ProviderResponse` com os campos `id`, `name`, `type`, `status`, `is_configured`, `has_credentials` e `avg_latency_ms` (opcional).

### `POST /providers`
Cadastra um provedor.

| Campo       | Tipo             | Obrigatório | Observações |
|-------------|------------------|-------------|-------------|
| `name`      | string           | sim         | Nome lógico (ex.: `360dialog`). |
| `type`      | string           | não         | Default `whatsapp`. |
| `base_url`  | string \| null | não         | URL base do conector. |
| `metadata`  | objeto           | não         | Guarda chaves específicas do provedor. |

**Respostas**
- `200 OK` – `ProviderResponse` recém-criado.
- `400 Bad Request` – falha de integridade (nome duplicado na org).

### `POST /providers/credentials`
Persistem credenciais criptografadas para o provedor.

| Campo             | Tipo   | Obrigatório | Observações |
|-------------------|--------|-------------|-------------|
| `provider_id`     | string | sim         | UUID do provedor (validação rígida). |
| `credentials`     | objeto | sim         | Payload serializado antes da criptografia. |

**Respostas**
- `200 OK` – `{ "status": "credentials_saved" }`.
- `400 Bad Request` – `Invalid provider_id` ou sem credenciais para health check.
- `404 Not Found` – provedor inexistente para a organização.

### `POST /providers/{provider_id}/health`
Executa o `health_check` do conector usando as credenciais ativas.

**Resposta 200**
```json
{
  "provider_id": "<uuid>",
  "provider_name": "360dialog",
  "healthy": false,
  "status_code": 401,
  "latency_ms": 123.4,
  "error": "..." // opcional
}
```
Erros: `400 Bad Request` (UUID inválido ou sem credenciais), `404 Not Found` para provedor inexistente.

### `DELETE /providers/{provider_id}/credentials`
Desativa credenciais ativas do provedor. Retorna `{"status":"credentials_removed"}` em `200 OK`. Erros: `400` (UUID inválido) e `404` (credenciais não encontradas).

## Regras de roteamento

### `GET /rules`
Retorna regras ordenadas por prioridade. Cada item inclui `conditions` e `actions` conforme armazenado.

### `POST /rules`
Cria nova regra.

| Campo           | Tipo          | Obrigatório | Observações |
|-----------------|---------------|-------------|-------------|
| `name`          | string        | sim         | Identificador amigável. |
| `is_enabled`    | boolean       | não         | Default `true`. |
| `conditions`    | array objeto  | sim         | Avaliadas pelo motor de roteamento. |
| `actions`       | objeto        | sim         | Deve incluir `primary_provider` com UUID válido. |
| `priority`      | inteiro       | não         | Default `100`. |

**Resposta 200** – objeto completo da regra. Erros de validação retornam `422`.

### `PATCH /rules/{rule_id}`
Atualiza a regra integralmente. Erros: `404` se o ID não pertence à organização.

### `POST /rules/{rule_id}/toggle`
Inverte `is_enabled` e retorna `{ "is_enabled": false }`. Erros: `404` para regra inexistente.

### `POST /rules/simulate`
Retorna os totais `baseline`, `optimized` e `saved` (inteiros em centavos) com base nas regras ativas.

### `POST /rules/simulate-advanced`
Resposta inclui:
- `total_baseline`, `total_optimized`, `total_saved`.
- `breakdown[]` com `country`, `volume`, `baseline_cost`, `optimized_cost`, `saved`, `providers[]` (detalhes por provedor) e `recommended_provider`.
- `recommended_route` mapeando país → UUID.

## Mensagens

### `POST /messages/send`
Agenda envio aplicando roteamento e fallback.

| Campo                | Tipo     | Obrigatório | Observações |
|----------------------|----------|-------------|-------------|
| `idempotency_key`    | string   | sim         | Requisições repetidas retornam o mesmo job. |
| `to_number`          | string   | sim         | Normalizado para E.164. |
| `template_id`        | string   | sim         | Identificador do template. |
| `template_category`  | string   | não         | Default `marketing`. |
| `variables`          | objeto   | não         | Valores aplicados ao template. |
| `country_iso`        | string   | não         | Inferido pelo número quando omitido. |

**Respostas principais**
- `200 OK` – `{ "job_id": "<uuid>", "status": "processing", "provider_used": "360dialog", "estimated_cost": 35, "message": "Message delivered successfully" }` (mensagem entregue ou em andamento).
- `400 Bad Request` – nenhum provedor disponível ou erro de roteamento persistido.
- `403 Forbidden` – contato com opt-out registrado (gera enfileiramento de reconfirmação).
- `429 Too Many Requests` – limite de envios por `org_id` excedido; inclui headers `Retry-After` e `X-RateLimit-Remaining: 0` para orientar o retry.
- Fluxos bem sucedidos criam `MessageEvent` vinculado ao `MessageJob` com `unit_cost_minor`, `baseline_cost_minor`, `currency`, `country_iso` e `template_name`, garantindo consistência das métricas.

**Circuit breaker & métricas**
- Falhas consecutivas por provedor são persistidas em Redis (`circuit:{provider_id}`) com limiar configurável via `CIRCUIT_BREAKER_THRESHOLD` e cooldown `CIRCUIT_BREAKER_COOLDOWN_SECONDS`.
- Estados `open` e `half-open` bloqueiam o provedor tanto no `RoutingEngine` quanto no fallback do envio, forçando o uso da cadeia restante.
- Sucessos zeram o contador e fecham o circuito. Falhas registram logs estruturados e alimentam `messages_delivery_attempts_total{outcome="failure|exception|success|skipped_circuit"}`.
- Métricas agregadas expostas em Prometheus: `messages_send_total` (status final), `messages_circuit_breaker_state{provider_id}` (0=closed,1=half-open,2=open).
- Para simular falha em sandbox, ajuste `SANDBOX_FAILURE_RATE` ou force respostas de erro nos conectores; após atingir o limiar, observe o bloqueio na próxima seleção.

### `GET /messages/jobs`
Lista até 100 jobs mais recentes. Filtros:
- `status` (enum `queued`, `processing`, `delivered`, `failed_final`, `delivered_with_fallback`). Valores inválidos → `400`.

**Resposta 200** – array com `id`, `status`, `to_number`, `template_id`, `template_category`, `country_iso`, `created_at`, `total_cost_minor`.

### `GET /messages/jobs/{job_id}`
Detalhes de um job e suas tentativas.

**Resposta 200**
```json
{
  "id": "<uuid>",
  "status": "delivered",
  "to_number": "+5511999999999",
  "template_id": "welcome",
  "template_category": "marketing",
  "country_iso": "BR",
  "created_at": "2025-10-09T11:20:00+00:00",
  "total_cost_minor": 35,
  "attempts": [
    {
      "id": "<uuid>",
      "attempt_number": 1,
      "status": "success",
      "provider_id": "<uuid>",
      "provider_name": "360dialog",
      "latency_ms": 1234,
      "error_code": null,
      "error_message": null
    }
  ]
}
```
Erros: `404 Not Found` para jobs inexistentes.

## Eventos

### `GET /events`
Consulta eventos de mensagens (inbound/outbound) armazenados.

Parâmetros opcionais: `limit` (máx. 1000), `offset`, `country`, `template`, `from`, `to` (ISO). Retorna lista com `direction`, `template_name`, `category`, `country_iso`, `timestamp_provider`, `delivery_status`, `unit_cost_minor`, `baseline_cost_minor`, `currency`.

## Tarifas

### `GET /rates`
Lista até 100 tarifas mais recentes com `provider_id`, `provider_name`, `effective_from`, `country_iso`, `category`, `template_name`, `unit_cost_minor`, `currency`. Ordenado por `effective_from DESC`.

### `POST /rates/import_csv`
Aceita arquivo CSV (campo `file`). Colunas obrigatórias: `effective_from`, `country_iso`, `category`, `unit_cost_minor`, `currency` e `provider_id` ou `provider_name`.

**Respostas**
- `200 OK` – `{ "imported": <n_linhas> }`.
- `400 Bad Request` – CSV sem identificador de provedor.
- `404 Not Found` – provedor inexistente.
- `422` – datas ou custos inválidos.

## Relatórios

### `GET /reports/summary`
Retorna custos e economia (últimos 7 dias por padrão ou intervalo customizado com `from`/`to`). Campos: `cost_7d_minor`, `saved_7d_minor`, `pct_saved`.

### `GET /reports/dashboard-metrics`
Métricas completas do dashboard para `days` (1–90):
- Totais (`total_messages`, `total_cost_minor`, `baseline_cost_minor`, `saved_minor`) alimentados diretamente por `MessageEvent`.
- `success_rate`, `avg_latency_ms`.
- `top_countries[]`, `top_templates[]` com `cost_minor` agregado.
- `alerts[]`, `recommendations[]` com mensagens em português.
Erros: valores fora do range retornam `422`.

### `GET /reports/provider-metrics`
Estatísticas por provedor: `provider_id`, `provider_name`, `total_sent`, `success_rate`, `avg_latency_ms`, `total_cost_minor`. Parâmetro `days` segue a mesma regra da rota anterior.

## Contatos

### `GET /contacts`
Retorna envelope com paginação (`items`, `limit`, `offset`, `count`). Filtros disponíveis: `status`, `channel`, `opt_in_status[]`, `segment_id[]`, `segment_slug[]`, `channel_address`. Requer permissão `contacts:read`.

### `POST /contacts/imports`
Upload assíncrono de CSV (`upload`). Retorna `202 Accepted` com `ContactImportJobResponse` contendo status, totais e URIs de relatório. Erros: `500` ao falhar a fila de importação.

### `POST /contacts`
Cria contato imediatamente.

Campos aceitos seguem `ContactCreate`: identificadores externos, `full_name`, `email`, `phone`, `attributes` (objeto), `source`, `source_metadata`, `status` (default `active`). Resposta `201 Created` com representação completa. Erros: `422` para telefone/e-mail inválidos.

### `PATCH /contacts/{contact_id}`
Atualiza parcialmente. Retorna contato atualizado ou `404` se não pertencer à organização.

### `DELETE /contacts/{contact_id}`
Remove contato e retorna `204 No Content`. `404` quando não encontrado.

### `GET /contacts/{contact_id}/consents/history`
Lista eventos de consentimento com `status`, `agent`, `evidence_uri`, `proof_hash`, `context`. `404` quando o contato não existe.

## Segmentos de contato

### `GET /contact-segments`
Retorna envelope com segmentos (`items`, `limit`, `offset`, `count`).

### `POST /contact-segments`
Cria segmento (`slug`, `name`, `description`, `criteria`, `source`, `source_metadata`). Resposta `201 Created` com o segmento. Erros: `422` para dados inválidos.

### `GET /contact-segments/{segment_id}`
Busca segmento específico. `404` se inexistente.

### `PATCH /contact-segments/{segment_id}`
Atualiza campos informados. `404` quando não encontrado.

### `DELETE /contact-segments/{segment_id}`
Remove segmento e memberships. Retorna `204`. `404` quando inexistente.

### `POST /contact-segments/{segment_id}/contacts`
Associa contatos ao segmento. Corpo segue `SegmentContactsRequest` (`contact_ids`, `membership_origin`, `source`, `source_metadata`). Resposta inclui `created_memberships`, `missing_contact_ids` e `already_associated`. `404` para segmento inexistente.

### `DELETE /contact-segments/{segment_id}/contacts/{contact_id}`
Remove associação. `404` se o contato não estava vinculado ao segmento. Retorna `204`.

### `PUT /contact-segments/{segment_id}/policy`
Upsert de políticas (`limits`, `opt_out`). Retorna objeto com limites e regras aplicadas. `404` se o segmento não existir.

## Integrações WhatsApp

### `POST /integrations/wa/connections`
Cria ou atualiza conexão WA.

| Campo                  | Tipo   | Obrigatório | Observações |
|------------------------|--------|-------------|-------------|
| `business_id`          | string | sim         | ID do Business Manager. |
| `phone_id`             | string | sim         | Identificador do número (único por org). |
| `access_token`         | string | sim         | Criptografado via `encrypt_token`. |
| `webhook_verify_token` | string | sim         | Validado para evitar duplicidade na mesma org. |
| `webhook_secret`       | string | sim         | Usado para assinar webhooks. |

**Respostas**
- `200 OK` – `{ "id": "<uuid>", "status": "active" }`.
- `400 Bad Request` – token de verificação duplicado ou erro de integridade.

### `GET /integrations/wa/webhook`
Valida webhook do Meta. Requer query `hub.mode=subscribe`, `hub.verify_token` e `hub.challenge`. Resposta `200` com o valor de `hub.challenge` quando o token existe; caso contrário `403`.

### `POST /integrations/wa/webhook`
Processa eventos assinados (`X-Hub-Signature-256: sha256=<hex>`). Regras atuais:

- Sem assinatura válida, sem conexão ativa ou `phone_number_id` desconhecido → `{ "status": "ignored", "processed": 0 }`.
- Se o número remetente existir no catálogo mas **não possuir opt-in ativo em `contact_channel_opt_in`**, é registrada uma ocorrência em `contact_consent_audit` (`status=revoked`, `source="webhook"`) e a API responde `{ "status": "denied" }`. A solicitação de opt-in pode ser re-enfileirada via `OptInRequestService` para follow-up.
- Eventos válidos geram registros `MessageEvent` com `contact_id` vinculado (quando o consentimento está ativo) e payload mascarado (`from`, `body`, `caption` etc. retornam `"***redacted***"`). A resposta inclui `{ "status": "ok", "processed": <n> }`.
- Erros de parse retornam `400` (`"Invalid payload"`).

O endpoint é idempotente por `provider_event_id`: eventos repetidos não criam duplicatas e reutilizam o mesmo hash de auditoria para negações.

### `POST /integrations/wa/test`
Retorna `{ "status": "ok", "message": "Test endpoint - no actual send" }` para verificações locais.

## Opt-in

### `POST /opt-in/webhook`
Confirma solicitações de opt-in provenientes de terceiros.

| Campo               | Tipo        | Obrigatório | Observações |
|---------------------|-------------|-------------|-------------|
| `request_id`        | UUID        | sim         | Identificador da solicitação criada anteriormente. |
| `org_id`            | UUID        | sim         | Tenant proprietário. |
| `status`            | string      | sim         | Apenas `confirmed` é processado. |
| `channel`           | string      | sim         | Ex.: `whatsapp`. |
| `channel_address`   | string      | sim         | Número/e-mail normalizado. |
| `agent`             | string/null | não         | Default `"webhook"`. |
| `legal_basis`       | string/null | não         | Finalidade legal. |
| `captured_at`       | datetime    | não         | Momento da captura. |
| `evidence_uri`      | string/null | não         | Link para evidência. |
| `proof_hash`        | string/null | não         | Hash de comprovação. |
| `metadata`          | objeto/null | não         | Chaves adicionais. |
| `request_ip`        | string/null | não         | IP da origem; se ausente é inferido do request. |

Headers: `X-Opt-In-Token` deve corresponder ao segredo configurado (`settings.OPT_IN_WEBHOOK_TOKEN`). Query opcional `async=true` enfileira o processamento.

**Respostas**
- `202 Accepted` – `{"status": "confirmed", ...}` com `opt_in_id` e `confirmed_at` quando processado inline.
- `202 Accepted` – `{"status": "enqueued"}` quando `async=true`.
- `403 Forbidden` – token inválido.
- `404 Not Found` – solicitação inexistente.
- `409 Conflict` – solicitação em estado não processável.

## Administração

### `GET /admin/health`
Resposta `{"status": "ok"}` para monitoramento básico.

### `GET /admin/metrics`
Exibe métricas Prometheus (`text/plain; version=0.0.4`). Cada chamada incrementa `app_requests_total` e `admin_metrics_scrapes_total`, atualiza `admin_metrics_last_scrape_timestamp` e reporta gauges `admin_circuit_breakers_open_total` / `admin_circuit_breakers_half_open_total`. **Importante**: rota ainda está pública; proteja-a antes de expor externamente.

## Recursos auxiliares

- [Coleção Postman](../postman/README.md)
- [Modelagem de dados](../architecture/DATA_MODEL.md)
- [Backlog priorizado](../backlog/README.md)
