[Docs](../overview/README.md) › [Operações](./OPERATIONS.md) › Migrations
# Guia de Migrations

A stack agora depende exclusivamente de migrations Alembic (sem `metadata.create_all`). A sequência recomendada garante que o schema esteja pronto **antes** da API e do worker inicializarem.

## Visão geral

| Revisão | Arquivo | Descrição |
|---------|---------|-----------|
| `000_base_schema` | `backend/alembic/versions/000_base_schema.py` | Cria todas as tabelas e enums atuais (orgs, providers, mensagens, rates, webhook, etc.). |
| `001_add_mvp_models` | `backend/alembic/versions/001_add_mvp_models.py` | Marcador histórico (no-op após consolidação do schema base). |
| `002_encrypt_provider_credentials` | `backend/alembic/versions/002_encrypt_provider_credentials.py` | Migra credenciais para criptografia Fernet (usa `APP_SECRET_KEY`). |

Nova migrations devem sempre apontar `down_revision` para a última revisão do quadro acima.

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
