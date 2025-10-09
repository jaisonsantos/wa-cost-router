# Snapshot — M1 — Migração e API base (2024-10-18)

## Resumo
- Migração `contact_profile` aplicada com rollback seguro e carga inicial validada em sandbox.
- API CRUD de contatos publicada com filtros por `org_id`, paginação e deduplicação por `wa_msisdn`.
- Importação CSV disponível via `/contacts/import`, rejeitando inconsistências e exportando relatório auditável.

## Entregáveis concluídos
- `alembic` ajustado para migrar dados legados e promover criptografia das colunas sensíveis.
- Guia operacional atualizado em [`docs/operations/MIGRATIONS.md`](../../operations/MIGRATIONS.md) para refletir a sequência `upgrade → seed → import`.
- Coleção Postman recebeu cenários de criação/atualização alinhados à nova API (`Contacts CRUD v2`).

## Evidências
- Execução de `make migrate` + `make seed` registrada no canal `#proj-wa-optin` com tempos médios < 3min.
- QA validou 42 casos de importação, incluindo duplicidades e remoção de caracteres especiais.

## Impacto nos casos de uso
- UC-01 avança para fase de **validação funcional**, habilitando construção de timeline de consentimento (pré-requisito de M2).
- Desbloqueia dependência `20251006-migration-base` no backlog priorizado.

## Próximos passos imediatos
- Concluir integração do histórico de consentimentos (M2) usando a trilha auditável criada na importação.
- Revisar políticas de sanitização antes do go-live do webhook multi-tenant.
