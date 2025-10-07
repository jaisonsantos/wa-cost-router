[Docs](../overview/README.md) › [API](./API_REFERENCE.md)
# Referência da API

Todas as rotas exigem `Authorization: Bearer <token>` salvo quando indicado. Exemplos abaixo assumem o ambiente local (`http://localhost:8000`). A coleção Postman (`docs/postman/wa-cost-router.postman_collection.json`) contém requisições nomeadas iguais às tabelas abaixo.

## Autenticação

| Método | Rota | Descrição | Postman |
|--------|------|-----------|---------|
| POST | `/auth/register` | Cria usuário + organização inicial. | `Auth - Register` |
| POST | `/auth/login` | Gera JWT para usuário existente. | `Auth - Login` |

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@demo.local","password":"demo123"}'
```

Tokens bem-sucedidos são salvos automaticamente na variável `token` pelo script de testes da coleção.

## Provedores

| Método | Rota | Descrição | Postman |
|--------|------|-----------|---------|
| GET | `/providers` | Lista provedores da organização. | `Providers - List` |
| POST | `/providers` | Cria provedor (usa `metadata` opcional). | `Providers - Create` |
| POST | `/providers/credentials` | Cria/atualiza credenciais (criptografadas). | `Providers - Save Credentials` |
| POST | `/providers/{id}/health` | Verifica conectividade com o conector. | `Providers - Health Check` |
| DELETE | `/providers/{id}/credentials` | Remove credenciais ativas. | `Providers - Delete Credentials` |

```bash
curl -X POST http://localhost:8000/providers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"360dialog","type":"whatsapp","metadata":{"region":"eu"}}'
```

## Regras de roteamento

| Método | Rota | Descrição | Postman |
|--------|------|-----------|---------|
| GET | `/rules` | Lista regras existentes. | `Rules - List` |
| POST | `/rules` | Cria regra (usa `provider_id` da variável Postman). | `Rules - Create` |
| PATCH | `/rules/{id}` | Atualiza regra completa. | `Rules - Update` |
| POST | `/rules/{id}/toggle` | Liga/desliga regra (retorna `{is_enabled}`). | `Rules - Toggle` |
| POST | `/rules/simulate-advanced` | Simula custos com regras atuais. | `Rules - Simulate Advanced` |

```bash
curl -X POST http://localhost:8000/rules/simulate-advanced \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"countries":["BR"],"volumes":{"BR":100},"category":"MARKETING"}'
```

## Mensagens

| Método | Rota | Descrição | Postman |
|--------|------|-----------|---------|
| POST | `/messages/send` | Inicia job de envio e retorna `job_id`. | `Messages - Send` |
| GET | `/messages/jobs` | Lista jobs com filtros opcionais (`status`). | `Messages - Jobs` |
| GET | `/messages/jobs/{job_id}` | Detalhes + tentativas (`DeliveryAttempt`). | `Messages - Job Detail` |

```bash
curl -X POST http://localhost:8000/messages/send \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"idempotency_key":"demo-001","to_number":"+5511999999999","template_id":"welcome","template_category":"MARKETING","variables":{}}'
```

## Tarifas

| Método | Rota | Descrição | Postman |
|--------|------|-----------|---------|
| GET | `/rates` | Lista tarifas ordenadas por `effective_from`. | `Rates - List` |
| POST | `/rates/import_csv` | Importa CSV (multipart) com tarifas. | `Rates - Import CSV` |

- As respostas de `/rates` incluem `provider_id`/`provider_name` para identificar o dono da tarifa.
- O CSV de importação deve conter a coluna `provider_id` apontando para um provedor existente da organização (veja `docs/postman/sample_rates.csv`).

## Relatórios

| Método | Rota | Descrição | Postman |
|--------|------|-----------|---------|
| GET | `/reports/dashboard-metrics` | KPIs de volume, economia e alertas. | `Reports - Dashboard Metrics` |
| GET | `/reports/provider-metrics` | Métricas agregadas por provedor. | `Reports - Provider Metrics` |
| GET | `/reports/summary` | (Opcional) Resumo agregado histórico. | `Reports - Summary` |

## Integrações WhatsApp

| Método | Rota | Descrição | Postman |
|--------|------|-----------|---------|
| POST | `/integrations/wa/connections` | Salva conexão WA (token + secret criptografados). | `WA - Create Connection` |
| GET | `/integrations/wa/webhook` | Validação de webhook (hub.verify_token). | `WA - Webhook Verify` |
| POST | `/integrations/wa/webhook` | Recebe eventos (requer `metadata.phone_number_id` + assinatura HMAC). | `WA - Webhook Receive` |

### Webhook WhatsApp

#### `GET /integrations/wa/webhook`

- Envie `hub.mode=subscribe`, `hub.verify_token=<token>` e `hub.challenge=<number>`.
- A API retorna `200` com o valor de `hub.challenge` **apenas** quando existe uma `WAConnection` ativa com o `webhook_verify_token` informado. Casos sem correspondência resultam em `403`.

#### `POST /integrations/wa/webhook`

- Obrigatório incluir o header `X-Hub-Signature-256: sha256=<HMAC>` calculado com o secret configurado para a conexão.
- O payload deve carregar `entry[].changes[].value.metadata.phone_number_id` para roteamento multi-tenant. Eventos de números desconhecidos são ignorados sem gravação.
- A assinatura é validada com HMAC SHA-256 sobre o corpo bruto; divergências retornam `403` e nenhum evento é persistido.

```bash
BODY='{
  "entry": [
    {
      "changes": [
        {
          "value": {
            "metadata": {"phone_number_id": "demo_phone_456"},
            "messages": [
              {"id": "msg-demo-1", "from": "demo_phone_456", "text": "hello"}
            ]
          }
        }
      ]
    }
  ]
}'
SECRET='my-webhook-secret'
SIGNATURE="sha256=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* //')"

curl -X POST http://localhost:8000/integrations/wa/webhook \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: $SIGNATURE" \
  -d "$BODY"
```

## Admin & Saúde

| Método | Rota | Descrição | Postman |
|--------|------|-----------|---------|
| GET | `/admin/health` | Health-check simples (usar internamente). | `Admin - Health` |
| GET | `/admin/metrics` | Métricas Prometheus (deve ser protegido). | `Admin - Metrics` |

## Veja também

- [Coleção Postman](../postman/README.md)
- [Modelagem de dados](../architecture/DATA_MODEL.md)
- [Backlog priorizado](../backlog/README.md)
