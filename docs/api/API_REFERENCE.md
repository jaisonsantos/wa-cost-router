[Docs](../current-cycle/README.md) › [API](./API_REFERENCE.md)
# Referência da API

Todas as rotas utilizam JSON e, salvo indicação contrária, exigem o header `Authorization: Bearer <token>`. Os exemplos assumem o ambiente local (`http://localhost:8000`) e estão sincronizados com a coleção Postman em `docs/postman/wa-cost-router.postman_collection.json`.

## Convenções gerais

- Erros de validação Pydantic/FastAPI retornam `422 Unprocessable Entity` com detalhes em `detail[].msg`.
- Identificadores seguem o formato UUID v4.
- Datas são serializadas em ISO 8601 com timezone UTC (`2025-10-09T11:30:00+00:00`).
- O Postman injeta automaticamente o token JWT ativo nas requisições por meio de script de pré-requisição.

## Fluxos multicanal, SLA e consentimento

- **Fluxo outbound** — `POST /messages/send` resolve o canal (`whatsapp`, `sms`, `email`*) a partir do payload, aplica o `RoutingEngine`
  com circuito de provedores por `org_id` e valida consentimento ativo antes de persistir o job. Endereços podem ser inferidos a
  partir do `contact_id` e preferências cadastradas. Jobs negados por consentimento retornam `403` e são auditados em
  `contact_consent_audit`.
- **Fluxo inbound multicanal** — os webhooks de WhatsApp e SMS mapeiam `phone_id`/`From` → `org_id`, verificam assinatura do
  provedor, mascaram PII e registram eventos apenas quando o contato possui opt-in ativo. Eventos negados disparam follow-up via
  `OptInRequestService`.
- **Medição de SLA** — Conversas inbound alimentam `sla_snapshot` e `queue_entry` por canal. Os endpoints
  `/reports/channel-metrics` e `/reports/queues` consolidam tempo médio de primeira resposta, backlog e taxa de cumprimento por
  canal, enquanto `/reports/dashboard-metrics` agrega custos, economia e alertas.
- **Consentimento** — `POST /opt-in/webhook` registra opt-ins versionados (com `proof_hash`/`evidence_uri`) e atualiza o estado em
  `contact_channel_opt_in`. O histórico completo pode ser consultado em `GET /contacts/{id}/consents/history`.

> *Suporte a `email` está em piloto fechado; usar apenas quando o tenant estiver habilitado nas configurações internas.

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

## Billing

### `POST /billing/usage/sync`
Agenda a sincronização das janelas de uso faturável com o Stripe. Disponível apenas quando `BILLING_USAGE_SYNC_ENABLED=true`.

**Headers obrigatórios**
- `Authorization: Bearer <token>`

**Resposta 202**
```json
{
  "job_id": "rq:job:usage:1a2b3c",
  "status": "enqueued"
}
```

O job é executado na fila `billing_usage` e respeita o batch configurado via `BILLING_USAGE_BATCH_SIZE`. Acompanhe o progresso pelo dashboard do RQ ou pelos logs (`event=billing_usage_batch`).

Erros: `503 Service Unavailable` quando a flag estiver desabilitada; demais erros seguem o padrão FastAPI.

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

**Resposta 200** – array de objetos `ProviderResponse` com os campos abaixo:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | string | UUID do provedor. |
| `name` | string | Nome lógico configurado pela organização. |
| `type` | string | Canal (`whatsapp`, `sms`, `email`, etc.). |
| `status` | string | `active`, `inactive` ou outros estados operacionais. |
| `is_configured` / `has_credentials` | boolean | Indicam se há credenciais ativas. |
| `avg_latency_ms` | number \| null | Média de latência coletada pelos health checks (opcional). |
| `metadata` | objeto | Metadados persistidos no cadastro (`channels`, notas de compliance, defaults). |
| `required_fields` | string[] | Lista de campos obrigatórios para `POST /providers/credentials`. |
| `provider_form_schema` | objeto | Esquema dinâmico utilizado pelo frontend/automação para renderizar formulários. |

Exemplo de item retornado:

```json
{
  "id": "ac9935b4-9a33-4aab-9ce4-3c9d9a5bd934",
  "name": "Twilio Sandbox",
  "type": "sms",
  "status": "active",
  "is_configured": true,
  "has_credentials": true,
  "metadata": {
    "provider": "twilio",
    "channels": {
      "sms": {
        "inbound_numbers": ["+15558675309"],
        "sandbox": true
      }
    },
    "compliance": {
      "registrations": ["Para produção, registre campanhas 10DLC."],
      "opt_in": "Exige consentimento explícito." 
    }
  },
  "required_fields": ["account_sid", "auth_token", "from_number"],
  "provider_form_schema": {
    "title": "Twilio SMS Sandbox",
    "fields": [
      { "key": "account_sid", "label": "Account SID", "type": "text", "required": true },
      { "key": "auth_token", "label": "Auth Token", "type": "password", "required": true },
      { "key": "from_number", "label": "Número remetente (E.164)", "type": "tel", "mask": "+###############" },
      { "key": "inbound_verify_token", "label": "Token de verificação inbound", "type": "text" }
    ],
    "consent_guidance": ["Certifique-se de que o opt-in foi documentado."],
    "testing_instructions": ["Execute o health check após salvar as credenciais."]
  }
}
```

O campo `provider_form_schema.fields` descreve cada input aceito pelo backend. Chaves comuns:

| Atributo | Significado |
|----------|-------------|
| `key` | Nome do campo enviado em `credentials`. |
| `label` | Texto exibido na UI. |
| `type` | `text`, `password`, `tel`, `email` ou `select`. |
| `mask` | Máscara opcional (ex.: `+###############` para números E.164). |
| `required` | Indica obrigatoriedade. |
| `validation.regex` | Expressão regular aplicada antes de persistir as credenciais. |
| `validation.message` | Mensagem amigável retornada em caso de formato inválido. |
| `help_text` / `consent_guidance` / `testing_instructions` | Notas operacionais exibidas no frontend. |

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
- `404 Not Found` – provedor inexistente para a organização.
- `422 Unprocessable Entity` – payload não atende aos campos obrigatórios/validações listados em `required_fields` ou no `provider_form_schema`.

#### Credenciais específicas — WhatsApp Cloud (Meta)

- `access_token` – token de acesso gerado no [Meta for Developers](https://developers.facebook.com/) com permissão para envio de mensagens WhatsApp Cloud.
- `phone_id` – identificador numérico do telefone (`phone_number_id`) usado na rota `https://graph.facebook.com/v19.0/{phone_id}/messages`.
- Opcionalmente é possível preencher defaults via variáveis de ambiente `settings.META_WHATSAPP_CLOUD_ACCESS_TOKEN` e `settings.META_WHATSAPP_CLOUD_PHONE_ID` para automações internas/sandbox.

> **Teste rápido**: após salvar as credenciais utilize `POST /providers/{provider_id}/health` para validar o token. A resposta `200` confirma que o Graph retornou o recurso `phone_id` com sucesso.

#### Campos obrigatórios por conector (sandbox)

- **Twilio (SMS)**
  - `account_sid` – `AC` + 32 caracteres hexadecimais. Ex.: `AC00000000000000000000000000000000`.
  - `auth_token` – string alfanumérica (16–64 caracteres) utilizada para assinar webhooks e autenticar REST.
  - `from_number` – número em formato E.164 habilitado no sandbox (ex.: `+15558675309`).
  - `inbound_verify_token` – token opcional para validar webhooks inbound (use o mesmo valor configurado no console Twilio).
  - **Notas regulatórias**: campanhas 10DLC exigem registro prévio e evidência de consentimento. Utilize o opt-in explícito e mantenha o inventário de números sandbox atualizado.
  - **Teste manual**: após salvar credenciais, execute `POST /providers/{provider_id}/health` ou o botão "Testar" na UI para confirmar `healthy=true`.

- **SendGrid (Email)**
  - `api_key` – chave iniciando em `SG.` com 16–128 caracteres permitidos (`[A-Za-z0-9_-]`).
  - `from_email` – remetente padrão validado (recomenda-se domínio autenticado em SPF/DKIM).
  - `webhook_token` – token utilizado pelo Event Webhook/Inbound Parse.
  - `inbound_signing_secret` – segredo para validar `X-Twilio-Email-Event-Webhook-Signature`/Parse (16–128 caracteres).
  - **Notas regulatórias**: habilite DKIM/SPF antes de sair do sandbox e respeite listas de supressão (`unsubscribe`). Mantenha provas de opt-in/double opt-in.
  - **Teste manual**: use `POST /integrations/email/test` ou dispare o request Postman correspondente após salvar as credenciais.

- **360dialog / Gupshup (WhatsApp)**
  - `access_token` (360dialog) ou (`api_key`, `app_name` para Gupshup) seguem inalterados, agora descritos via `provider_form_schema`.

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

## Templates

Catálogo de templates WhatsApp sincronizado com provedores conectados.

### `GET /templates`
Lista templates cadastrados para a organização. Parâmetros opcionais de query:

| Parâmetro | Tipo | Observações |
|-----------|------|-------------|
| `language` | string | Filtra pelo código do idioma (`pt_BR`, `en_US`, ...). Comparação case-insensitive. |
| `status` | string | Filtra pelo status normalizado (`approved`, `rejected`, `pending`, ...). |

**Resposta 200** – array de objetos com `id`, `name`, `category`, `language`, `status` e `meta`. O campo `meta` inclui apenas chaves curadas utilizadas nas políticas de envio (`blocked_countries`, `allowed_countries`, `blocked_hours`, `allowed_hours`) já normalizadas (códigos ISO em maiúsculo, janelas `HH:MM-HH:MM`, entradas duplicadas/ inválidas removidas).

### `POST /templates`
Cria um template manualmente.

| Campo | Tipo | Obrigatório | Observações |
|-------|------|-------------|-------------|
| `name` | string | sim | Nome único por idioma. |
| `category` | string | sim | Ex.: `marketing`, `utility`. |
| `language` | string | sim | Código BCP47 (`pt_BR`, `en_US`). |
| `status` | string | sim | Estado atual do template (`approved`, `rejected`, ...). |
| `meta` | objeto | não | Aceita apenas listas de `blocked_countries`, `allowed_countries`, `blocked_hours` e `allowed_hours`. Valores são normalizados (maiúsculas, faixas válidas) e itens inválidos são descartados. |

**Resposta 201** – template criado.

### `PATCH /templates/{template_id}`
Atualiza parcialmente um template (campos opcionais `name`, `category`, `language`, `status`, `meta`). Erros: `400` para UUID inválido e `404` quando não pertence à organização.

### `DELETE /templates/{template_id}`
Remove o template informado. Resposta `204 No Content` quando sucesso. `404` se não existir.

### `POST /templates/sync`
Sincroniza templates a partir dos provedores WhatsApp ativos (360dialog, Gupshup, Cloud). Para cada provedor com credenciais válidas:

- Consulta `list_templates` no conector, cria/atualiza registros locais combinando `name` + `language` e persiste somente os metadados relevantes (`blocked_countries`, `allowed_countries`, `blocked_hours`, `allowed_hours`), normalizando listas e removendo valores vazios. Caso o provedor deixe de informar restrições, o `meta` local é limpo.
- Retorna resumo com `providers[]` (nome do provedor, total sincronizado, idiomas e status encontrados) e listas agregadas `languages`, `statuses` para a organização.
- Campo `synced` indica o total de templates processados na execução.

Erros individuais de provedores são reportados por item (`providers[].error`) sem abortar a sincronização dos demais.

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
| `channel`            | string   | sim         | `whatsapp`, `sms` ou `email` (pilot). Normalizado automaticamente. |
| `template_id`        | string   | sim         | Identificador do template (nome ou UUID sincronizado em `/templates`). |
| `template_category`  | string   | não         | Default `marketing`. |
| `variables`          | objeto   | não         | Valores aplicados ao template. |
| `contact_id`         | UUID     | condicional | Obrigatório quando `channel_address` estiver vazio; permite inferir endereço preferencial. |
| `channel_address`    | string   | condicional | Telefone (E.164) ou e-mail normalizado. Validado conforme o canal. |
| `country_iso`        | string   | não         | Inferido a partir do contato/endereço quando omitido. |

**Respostas principais**
- `200 OK` – `{ "job_id": "<uuid>", "status": "processing", "provider_used": "360dialog", "estimated_cost": 35, "message": "Message delivered successfully" }` (mensagem entregue ou em andamento).
- `400 Bad Request` – nenhum provedor disponível ou erro de roteamento persistido.
- `403 Forbidden` – contato com opt-out registrado (gera enfileiramento de reconfirmação e auditoria em `contact_consent_audit`) **ou** violação de política do template (`detail.code` expõe o motivo, ex.: `template_blocked_country`).
- `429 Too Many Requests` – limite de envios por `org_id` excedido; inclui headers `Retry-After` e `X-RateLimit-Remaining: 0` para orientar o retry.
- Fluxos bem sucedidos criam `MessageEvent` vinculado ao `MessageJob` com `unit_cost_minor`, `baseline_cost_minor`, `currency`, `country_iso` e `template_name`, garantindo consistência das métricas.
- Cada tentativa (incluindo fallback) gera um registro em `routed_action` com `rule_id`, provedor selecionado, custo estimado (`cost_minor`), resposta do conector (`provider_response.connector_response`) e status final. Os eventos `MessageEvent` armazenam `attributes.routing_rule_name` e `attributes.provider_id` para auditoria do provedor vencedor.

Quando apenas `contact_id` é informado, o serviço resolve o endereço prioritário considerando opt-ins ativos por canal
(`MultiChannelConsentResolver`). Caso nenhum endereço elegível seja encontrado o retorno é `422 Unable to resolve channel address`.

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

### `GET /messages/jobs/{job_id}/routing`
Retorna a trilha de decisões (`RoutedAction`) gravada durante o envio, incluindo tentativas de fallback.

**Resposta 200**
```json
{
  "job_id": "<uuid>",
  "actions": [
    {
      "id": "<uuid>",
      "rule_id": "<uuid>",
      "rule_name": "route-sms-1a2b3c",
      "status": "failed",
      "provider_id": "<uuid>",
      "provider_name": "Twilio Primary",
      "attempt_number": 1,
      "cost_minor": 320,
      "connector_response": null,
      "created_at": "2025-10-09T11:21:00+00:00",
      "message_event_id": null
    },
    {
      "id": "<uuid>",
      "rule_id": "<uuid>",
      "rule_name": "route-sms-1a2b3c",
      "status": "delivered_with_fallback",
      "provider_id": "<uuid>",
      "provider_name": "Fallback Nexmo",
      "attempt_number": 2,
      "cost_minor": 175,
      "connector_response": {"status": "ok"},
      "created_at": "2025-10-09T11:21:02+00:00",
      "message_event_id": "<uuid>"
    }
  ]
}
```
Erros: `404 Not Found` quando o job não pertence à organização autenticada ou não existe.

### `POST /messages/jobs/{job_id}/dry-run`
Simula novamente o roteamento do job sem alterar estado, registrando um `RoutedAction` marcado com `dry_run: true` e retornando a cadeia atualizada.

**Resposta 200**
```json
{
  "job_id": "<uuid>",
  "actions": [
    {
      "id": "<uuid>",
      "rule_id": "<uuid>",
      "rule_name": "route-sms-1a2b3c",
      "status": "dry_run",
      "provider_id": "<uuid>",
      "provider_name": "Twilio Primary",
      "attempt_number": null,
      "cost_minor": 180,
      "connector_response": null,
      "created_at": "2025-10-09T11:21:05+00:00",
      "message_event_id": null,
      "dry_run": true
    }
  ]
}
```
Erros: `400 Bad Request` quando nenhuma rota elegível é encontrada, `403 Forbidden` (opt-out ou política violada) e `404 Not Found` para jobs inexistentes ou fora do escopo da organização.

Observações:
- A simulação registra um novo item na cadeia com `dry_run: true`, preservando status original do job e suas tentativas reais.
- O payload associado ao `RoutedAction` é sanitizado (`fallback_chain`, `provider_id`, `provider_name`) e serve apenas para auditoria.

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

### `GET /reports/summary/export`
Exporta o mesmo conjunto de dados do resumo em CSV (padrão) ou JSON via streaming.

- Parâmetros: `from`, `to` (ISO 8601) e `format` (`csv` ou `json`, default `csv`).
- Cabeçalhos: `Content-Type` varia conforme o formato (`text/csv; charset=utf-8` ou `application/json`), sempre com `Content-Disposition: attachment; filename="summary-report.<ext>"`.
- CSV inclui colunas `cost_7d_minor`, `saved_7d_minor`, `pct_saved`.

### `GET /reports/dashboard-metrics`
Métricas completas do dashboard para `days` (1–90):
- Totais (`total_messages`, `total_cost_minor`, `baseline_cost_minor`, `saved_minor`) alimentados diretamente por `MessageEvent`.
- `success_rate`, `avg_latency_ms`.
- `top_countries[]`, `top_templates[]` com `cost_minor` agregado.
- `alerts[]`, `recommendations[]` com mensagens em português.
Erros: valores fora do range retornam `422`.

### `GET /reports/provider-metrics`
Estatísticas por provedor: `provider_id`, `provider_name`, `total_sent`, `success_rate`, `avg_latency_ms`, `total_cost_minor`. Parâmetro `days` segue a mesma regra da rota anterior.

### `GET /reports/provider-metrics/export`
Streaming dos mesmos dados agregados por provedor.

- Parâmetros: `days` (1–90, default 7) e `format` (`csv` ou `json`).
- `Content-Disposition: attachment; filename="provider-metrics-report.<ext>"`.
- CSV apresenta as colunas `provider_id`, `provider_name`, `total_sent`, `success_rate`, `avg_latency_ms`, `total_cost_minor`.

### `GET /reports/channel-metrics`
Consolida dados de SLA por canal a partir de `sla_snapshot`. Aceita `from` e `to` em ISO 8601 (default: últimos 7 dias). Cada item retorna:
- `conversations_opened`/`conversations_closed` agregados no período.
- `backlog` com os valores mais recentes de `open`, `pending` e `closed`.
- `first_response.average_seconds` ponderado pelo volume de conversas respondidas.
- `sla` com `target_seconds`, total de conversas rastreadas e `compliance_rate` (% dentro do alvo de FRT).

**Resposta 200**
```json
[
  {
    "channel": "whatsapp",
    "conversations_opened": 128,
    "conversations_closed": 110,
    "backlog": {
      "open": 9,
      "pending": 4,
      "closed": 110
    },
    "first_response": {
      "average_seconds": 38.6,
      "sample_size": 110
    },
    "sla": {
      "target_seconds": 60.0,
      "within_target": 98,
      "total_tracked": 110,
      "compliance_rate": 89.09
    }
  }
]
```

### `GET /reports/channel-metrics/export`
Exporta as métricas por canal com suporte a CSV/JSON.

- Parâmetros: `from`, `to` e `format` (`csv` ou `json`).
- Arquivo fornecido com `Content-Disposition: attachment; filename="channel-metrics-report.<ext>"`.
- CSV inclui backlog (`open`, `pending`, `closed`), dados de primeira resposta e metadados de SLA para cada canal.

### `GET /reports/queues`
Mostra a saúde das filas de atendimento calculada a partir de `queue_entry`. Aceita `from` e `to` (ISO 8601, default: últimos 7 dias). Para cada canal são retornados:
- `backlog` com contagem de itens `open`, `responded`, `closed` e `total` no recorte.
- `first_response.average_seconds` baseado na média de `first_response_latency_seconds` das entradas respondidas.
- `sla` herdando o alvo e a taxa de cumprimento agregada em `sla_snapshot`.

**Resposta 200**
```json
[
  {
    "channel": "whatsapp",
    "backlog": {
      "open": 6,
      "responded": 3,
      "closed": 94,
      "total": 103
    },
    "first_response": {
      "average_seconds": 41.3,
      "sample_size": 97
    },
    "sla": {
      "target_seconds": 60.0,
      "within_target": 90,
      "total_tracked": 103,
      "compliance_rate": 87.38
    }
  }
]
```

### `GET /reports/queues/export`
Disponibiliza o mesmo payload das filas em CSV/JSON.

- Parâmetros: `from`, `to` e `format` (`csv` ou `json`).
- Cabeçalho `Content-Disposition` utiliza `queue-metrics-report.<ext>` como nome do arquivo.
- CSV traz colunas para backlog (`open`, `responded`, `closed`, `total`), métricas de primeira resposta e indicadores de SLA.

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

## Integrações multicanal

### `GET /integrations/connections`
Consolida o status das conexões configuradas para a organização autenticada. Retorna uma lista de objetos com os campos:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `id` | string | Identificador da conexão (UUID do `wa_connection` ou `provider`). Pode ser vazio quando o canal ainda não foi provisionado. |
| `channel` | string | Canal (`whatsapp`, `email`, `sms`, `telegram`, ...). |
| `display_name` | string | Rótulo amigável apresentado na UI. |
| `status` | string | Estado agregado (`healthy`, `warning`, `error`, `disconnected`, `unknown`). |
| `connected` | boolean | Indica se há configuração ativa/credenciais válidas para o canal. |
| `has_credentials` | boolean | `true` quando credenciais criptografadas estão ativas. |
| `metadata` | objeto | Metadados não sensíveis (ex.: `business_id`, `provider_name`, `provider_id`, `base_url`). |
| `last_health_check` | objeto ou `null` | Último snapshot persistido pelo teste de saúde: `{ healthy, status_code, latency_ms, error, checked_at, details }`. |

Exemplo de resposta:

```json
[
  {
    "id": "d7344f26-7a04-4f3f-8f3f-1234567890ab",
    "channel": "whatsapp",
    "display_name": "WhatsApp Business Cloud API",
    "status": "healthy",
    "connected": true,
    "has_credentials": true,
    "metadata": {
      "business_id": "1234567890",
      "phone_id": "9876543210",
      "connection_id": "d7344f26-7a04-4f3f-8f3f-1234567890ab"
    },
    "last_health_check": {
      "healthy": true,
      "status_code": "200",
      "latency_ms": 84,
      "checked_at": "2024-10-18T12:34:56+00:00",
      "details": {
        "status": "active"
      }
    }
  },
  {
    "id": "b10221a4-1dbe-49da-93e1-abcdefabcdef",
    "channel": "email",
    "display_name": "Email (SendGrid)",
    "status": "warning",
    "connected": true,
    "has_credentials": true,
    "metadata": {
      "provider_name": "SendGrid",
      "provider_type": "email",
      "provider_id": "b10221a4-1dbe-49da-93e1-abcdefabcdef"
    },
    "last_health_check": {
      "healthy": true,
      "status_code": 299,
      "latency_ms": 125,
      "checked_at": "2024-10-18T12:35:02+00:00"
    }
  }
]
```

### `POST /integrations/{channel}/test`
Executa o health check do canal informado (`whatsapp`, `email`, `sms`, ...). Para canais baseados em provedores é possível informar o `provider_id` explicitamente no corpo.

| Campo | Local | Tipo | Obrigatório | Descrição |
| --- | --- | --- | --- | --- |
| `channel` | path | string | sim | Canal alvo (`whatsapp`, `email`, `sms`). |
| `provider_id` | body | string | opcional | UUID do provedor (necessário quando existem múltiplos provedores por canal). |

**Respostas**

- `200 OK` – Snapshot de saúde: `{ "channel": "email", "status": "error", "healthy": false, "status_code": 503, "latency_ms": 910, "error": "Timeout", "checked_at": "2024-10-18T12:36:10+00:00", "metadata": { "provider_id": "...", "provider_name": "SendGrid" } }`.
- `400 Bad Request` – canal não suportado ou credenciais ausentes.
- `404 Not Found` – conexão/provedor não configurado para a organização.

## Integrações CRM

### `POST /integrations/crm/{slug}/webhook`
Recebe eventos outbound de CRMs suportados (ex.: HubSpot). O tenant é identificado via query `org_id=<uuid>` e o `slug` deve existir no registro (`hubspot`, `pipedrive`, ...).

**Headers obrigatórios**

- `Content-Type: application/json`
- `X-HubSpot-Signature`: assinatura `hex(hmac_sha256(CRM_WEBHOOK_SECRET, raw_body))`

**Respostas**

- `200 OK` – resumo `SyncResult`:

  ```json
  {
    "processed_contacts": 3,
    "has_more": false,
    "next_cursor": null,
    "last_change_at": "2024-12-01T10:15:30+00:00",
    "origin": "webhook"
  }
  ```

- `401 Unauthorized` – assinatura inválida (`detail: "Invalid signature"`).
- `404 Not Found` – `slug` desconhecido ou provedor não configurado para a organização.
- `409 Conflict` – credenciais ausentes/ inativas para o provedor CRM.
- `400 Bad Request` – payload JSON inválido.
- `502 Bad Gateway` – erro propagado do conector CRM (`ProviderSyncError`).

### `POST /integrations/crm/{slug}/poll`
Aciona manualmente a sincronização incremental de fallback (`CRMIncrementalSyncService.run_polling_cycle`). O corpo aceita parâmetros opcionais:

| Campo       | Tipo      | Obrigatório | Observações |
|-------------|-----------|-------------|-------------|
| `since`     | datetime  | não         | ISO 8601; sobrescreve `last_change_at` salvo em `meta.crm_sync`. |
| `page_size` | integer   | não         | Tamanho da página solicitado ao provedor (mínimo 1, default `CRM_MAX_PAGE_SIZE`). |

Respostas seguem o mesmo formato de `SyncResult`. Erros `404`/`409`/`502` refletem os mesmos cenários do webhook. Utilize para validação operacional após incidentes ou para monitoramento controlado.

## Integrações SMS
## Integrações SMS

### `POST /integrations/sms/webhook`
Recebe callbacks do Twilio (`application/x-www-form-urlencoded`). Valida assinatura `X-Twilio-Signature` usando o `auth_token`
armazenado nas credenciais do provedor e identifica o tenant pelo número de destino (`To`) ou `MessagingServiceSid`.

**Fluxo padrão**

- Eventos sem `MessageSid` ou com assinatura inválida retornam `403`.
- Quando o contato associado não possui opt-in ativo para SMS, a resposta é `{ "status": "denied" }`, o payload é mascarado e um
  follow-up é enfileirado em `OptInRequestService`.
- Mensagens aceitas geram `MessageEvent` com `channel="sms"`, `direction="inbound"`, `delivery_status` herdado do payload e
  campos sensíveis mascarados (`body`, `from`, `to`). A resposta inclui `{ "status": "ok", "processed": 1 }`.

**Headers de resposta** — `X-Webhook-Channel: sms` indica o canal que processou o evento. Falhas internas retornam `500` com log
`event=sms_webhook_failure`.

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
