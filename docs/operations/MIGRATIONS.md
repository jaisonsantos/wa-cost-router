[Docs](../current-cycle/README.md) › [Operações](./OPERATIONS.md) › Migrations
# Guia de Migrations

A stack agora depende exclusivamente de migrations Alembic (sem `metadata.create_all`). A sequência recomendada garante que o schema esteja pronto **antes** da API e do worker inicializarem.

## Visão geral

| Revisão | Arquivo | Descrição |
|---------|---------|-----------|
| `000_base_schema` | `backend/alembic/versions/000_base_schema.py` | Cria todas as tabelas e enums atuais (orgs, providers, mensagens, rates, webhook, etc.). |
| `001_add_mvp_models` | `backend/alembic/versions/001_add_mvp_models.py` | Marcador histórico (no-op após consolidação do schema base). |
| `002_encrypt_provider_credentials` | `backend/alembic/versions/002_encrypt_provider_credentials.py` | Migra credenciais para criptografia Fernet (usa `APP_SECRET_KEY`). |
| `003_add_message_job_fk` | `backend/alembic/versions/003_add_message_job_fk.py` | Conecta `message_event.message_job_id` e garante integridade básica. |
| `004_add_wa_webhook_secret` | `backend/alembic/versions/004_add_wa_webhook_secret.py` | Adiciona `webhook_secret_enc` a `wa_connection` e inicialmente impõe `webhook_verify_token` único. |
| `005_link_rate_cards_to_providers` | `backend/alembic/versions/005_link_rate_cards_to_providers.py` | Adiciona `provider_id` a `rate_card`, faz backfill por nome e remove registros órfãos. |
| `006_relax_wa_verify_token_scope` | `backend/alembic/versions/006_relax_wa_verify_token_scope.py` | Restringe a unicidade de `webhook_verify_token` ao par (`org_id`, token). |
| `007_add_contact_domain` | `backend/alembic/versions/007_add_contact_domain.py` | Cria o catálogo de contatos multi-tenant (contatos, opt-ins, segmentos, import jobs) com enums dedicados. |
| `008_add_contact_consent_audit` | `backend/alembic/versions/008_add_contact_consent_audit.py` | Introduz a trilha de auditoria de consentimento com índices por canal e `recorded_at`. |
| `009_add_contact_segment_policy` | `backend/alembic/versions/009_add_contact_segment_policy.py` | Acrescenta políticas por segmento (`limits`, `opt_out`) e garante relacionamento 1:1. |

Nova migrations devem sempre apontar `down_revision` para a última revisão do quadro acima.

### Notas por revisão

- **`004_add_wa_webhook_secret`**:
  - Requer `APP_SECRET_KEY` consistente para recriptografar segredos legados durante o upgrade.
  - Upgrade: `docker-compose run --rm api alembic upgrade 004_add_wa_webhook_secret` (ou `head`).
  - Rollback: `docker-compose run --rm api alembic downgrade 003_add_message_job_fk`.
- **`005_link_rate_cards_to_providers`**:
  - Remove `rate_card` sem provedor associado e força o relacionamento FK (impacta seeds antigos).
  - Após o upgrade, reexecute `make seed` para gerar o provedor demo com tarifas vinculadas.
- **`006_relax_wa_verify_token_scope`**:
  - Dropa a unique global de `webhook_verify_token` em `wa_connection` e cria unique composta por `org_id` + token.
  - Permite que ambientes de demo reutilizem tokens padrão (ex.: `my-verify-token`) sem conflitar com o seed.
- **`007_add_contact_domain`**:
  - Cria tabelas de contatos, opt-ins, segmentos e jobs de importação. Executa criação condicional de enums (`contactstatusenum`, `optinstatusenum`, `contactimportstatusenum`).
  - Exige que `DATABASE_URL` aponte para Postgres 12+ (uso de `JSON` e índices compostos). Após o upgrade, reexecute `make seed` apenas se precisar de dados demo.
- **`008_add_contact_consent_audit`**:
  - Deve ser aplicada logo após `007`. Armazena eventos de consentimento imutáveis com `request_ip` e `evidence_uri`.
  - Certifique-se de que o bucket de storage está configurado antes de habilitar o fluxo de importação (relatórios referenciam o job via `source_metadata`).
- **`009_add_contact_segment_policy`**:
  - Popula políticas padrão (`limits` e `opt_out` vazios) para segmentos existentes. Upgrade idempotente: se não houver segmentos, nada é criado.
  - Requer revisão das automações que consultam segmentos para considerar o campo `policy`.

## Execução local

```bash
make migrate         # roda alembic upgrade head
make seed            # popula dados demo, sem criar tabelas
```

O alvo `make dev` já executa `make migrate` automaticamente antes de subir API/worker.

## Pipeline manual (produção)

1. **Preparar ambiente**: exporte `DATABASE_URL`, `APP_SECRET_KEY` e `JWT_SECRET` com valores fortes. (`APP_SECRET_KEY` default "please-change-me" é apenas para desenvolvimento — veja backlog P1 "enforce secret strength").
2. **Executar migrations**:
   ```bash
   docker-compose run --rm api alembic upgrade head
   ```
3. **Opcional**: rodar seeds somente em ambientes de demo (`docker-compose run --rm api python scripts/seed.py`).
4. **Subir serviços**: iniciar API, worker e web somente após migrations concluídas.

## Validação pós-upgrade

- Verifique tabelas críticas:
  ```bash
  docker-compose exec db psql -U postgres -d wa_cost_router -c "\d provider"
  docker-compose exec db psql -U postgres -d wa_cost_router -c "\d message_job"
  ```
- Confirme enums: `SELECT unnest(enum_range(NULL::jobstatusenum));`
- Para migration `002`, confirme que `provider_credential.credentials_encrypted` contém texto Fernet (`startswith('gAAAA')`).

## Resolução de problemas

| Sintoma | Ação |
|---------|------|
| `relation "..." already exists` ao rodar `000_base_schema` | Banco não estava vazio. Faça backup e recrie o banco ou aplique scripts manuais com `ALTER TABLE ... IF NOT EXISTS`. |
| `APP_SECRET_KEY` usando valor padrão | Migrations e runtime não falham, mas registre uma tarefa operacional (ver backlog) para forçar secrets fortes em produção. |
| Falha em `002` por secret incorreto | Ajuste `APP_SECRET_KEY` para o valor antigo utilizado na criptografia anterior antes de reaplicar. |
| Necessidade de gerar nova migration | Use `make makemigration name=<slug>` e revise diffs antes de aplicar. |

## Boas práticas

- Sempre commitar migrations junto com alterações de modelos Pydantic/SQLAlchemy.
- Atualize `docs/architecture/DATA_MODEL.md` quando adicionar tabelas/colunas relevantes.
- Seeds **nunca** devem chamar `Base.metadata.create_all`; mantenha-os idempotentes.
- Rode `make postman-test` após migrations que alteram contratos de API.

## Veja também

- [Operações & runbooks](./OPERATIONS.md)
- [Guia de deploy](./DEPLOYMENT.md)
- [Backlog priorizado](../backlog/README.md)
