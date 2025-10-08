---
title: "Alinhar bancos legados à migration 000_base_schema"
type: tech-debt
prio: P1
estimate: "2d"
owner: "unassigned"
depends_on: []
---

> - **Status:** Pendente
> - **Caso de uso:** [UC-01 — Gestão de contatos unificada](../current-cycle/USE_CASE_TRACEABILITY.md#uc-01--gest%C3%A3o-de-contatos-unificada)

## Contexto

Criamos a migration [`000_base_schema`](../operations/MIGRATIONS.md) para substituir o seed `metadata.create_all`. Ambientes que já estavam em operação podem possuir schema divergente e precisam ser reconciliados antes da próxima release.

## Escopo

- Levantar bancos existentes (piloto interno) e validar diffs usando `alembic history` + inspeção manual.
- Gerar script de correção (SQL) para ajustar colunas/constraints sem perda de dados.
- Documentar o procedimento de atualização/rollback.
- Automatizar verificação em pipelines (ex.: rodar `alembic upgrade head` em CI com banco limpo).

## Acceptance Criteria

- Todos os ambientes apontam para `alembic_version = 000_base_schema` antes de aplicar novas revisões.
- Seed (`make seed`) funciona sem erros após executar migrations em banco existente.
- Guia de [Migrations](../operations/MIGRATIONS.md) atualizado com passos para ambientes herdados.

## Subtasks

- [ ] Coletar dump do banco legado e rodar `alembic upgrade head` em sandbox para validar compatibilidade.
- [ ] Criar script de ajuste (ALTER TABLE/UPDATE) para dados fora do padrão.
- [ ] Atualizar pipeline CI para executar `make migrate` automaticamente.
- [ ] Comunicar squads sobre o freeze necessário durante a migração.

## Referências

- [Guia de migrations](../operations/MIGRATIONS.md)
- [Seed script](../../backend/scripts/seed.py)
- [Modelagem de dados](../architecture/DATA_MODEL.md)

## Out of Scope

- Refatoração adicional de models além do que já está coberto pela migration base.
- Implementação de rollback automático para migrations futuras.
