# Modelagem de Dados

## Principais Entidades

| Tabela | Campos-chave | Notas |
| --- | --- | --- |
| `organization` | `id`, `name` | Tenant. |
| `user`, `organization_user` | `email`, `role`, `org_id` | `role` enum (`owner`, `member`). |
| `provider` | `org_id`, `name`, `type`, `status` | Unique `(org_id,name)`. |
| `provider_credential` | `org_id`, `provider_id`, `credentials_encrypted` | Credenciais criptografadas via Fernet. |
| `routing_rule` | `org_id`, `conditions_json`, `actions_json`, `priority`, `is_enabled` | JSON com condicionais e provedores. |
| `message_job` | `org_id`, `idempotency_key`, `status` | Unique `(org_id,idempotency_key)`. |
| `delivery_attempt` | `message_job_id`, `provider_id`, `attempt_number`, `status`, `provider_response` | Armazena resposta crua. |
| `cost_record` | `message_job_id`, `provider_id`, `price_eur`, `price_table_version` | Auditoria de custo. |
| `message_event` | `org_id`, `provider_event_id`, `unit_cost_minor`, `baseline_cost_minor` | Base para relatórios. |
| `rate_card` | `source`, `country_iso`, `category`, `unit_cost_minor` | Global (sem `org_id`). |
| `wa_connection` | `org_id`, `business_id`, `phone_id`, `access_token_enc` | Token WhatsApp criptografado. |

## ERD (ASCII)

```
organization ──< organization_user >── user
     │                             
     ├──< provider ──< provider_credential
     │         │
     │         └──< message_job ──< delivery_attempt
     │                           └──< cost_record
     │
     ├──< routing_rule
     ├──< message_event
     └──< wa_connection

rate_card (global, referenciado por nome do provider)
```

## Índices & Constraints

- `message_job`: unique `(org_id,idempotency_key)`, index em `created_at`.
- `provider`: unique `(org_id,name)`, índice `org_id`.
- `delivery_attempt`: PK UUID, considerar índice em `(message_job_id, attempt_number)`.
- `message_event`: índices em `org_id`, `provider_event_id`, `timestamp_provider`.

## Observações

- Migration 002 converte credenciais para texto criptografado.
- `rate_card` deveria incluir `org_id` se houver tarifas específicas por tenant.
- `provider_response` e `variables` precisam de sanitização/anonimização.
