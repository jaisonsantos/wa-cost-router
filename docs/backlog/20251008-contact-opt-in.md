---
title: "Catalogar opt-ins multicanal com auditoria"
type: feature
prio: P0
estimate: "5d"
owner: "squad-core-routing"
depends_on:
  - 20251006-migration-base
  - 20251006-sanitizacao-pii
status: Concluído
---

## Contexto

O piloto externo exige que o catálogo de contatos armazene opt-ins multicanal com histórico auditável. Antes desta entrega, a
aplicação só validava números durante o envio, sem trilha de consentimento ou versionamento.

## Escopo entregue

- APIs FastAPI `/contacts`, `/contacts/{id}/consents/history` e `/contacts/imports` com filtros por canal/segmento e integração ao
  motor de roteamento.
- Schemas Pydantic em [`backend/app/schemas/contacts.py`](../../backend/app/schemas/contacts.py) garantindo contratos alinhados ao
  frontend e à coleção Postman.
- Worker RQ para importação CSV assíncrona com relatório de erros, status de job e testes em [`backend/tests/worker/test_contact_import.py`](../../backend/tests/worker/test_contact_import.py).
- Documentação operacional atualizada (`docs/operations/RUNBOOK_CONTACTS.md`, `docs/security/PRIVACY_CONTROLS.md`) reforçando
  requisitos LGPD/GDPR.

## Critérios de aceite

- [x] Histórico de consentimento por canal visível na SPA e disponível via API.
- [x] Importação CSV aceita cabeçalhos obrigatórios e gera relatório de inconsistências.
- [x] Integrações CRM (HubSpot/Pipedrive) sincronizam alterações incrementais sem duplicar opt-ins.
- [x] Postman e pipelines CI cobrem os novos endpoints.

## Evidências

- ADR [`20251008-contact-domain`](../current-cycle/adr/20251008-contact-domain.md).
- Migrations Alembic `007-009` documentadas em [`docs/operations/MIGRATIONS.md`](../operations/MIGRATIONS.md).
- Testes automatizados: `backend/tests/api/test_contacts_validation.py`, `backend/tests/services/test_contacts_repository.py`,
  `backend/tests/worker/test_contact_import.py` e `src/pages/Contacts/__tests__/*`.

## Follow-ups

- Concluir hardening do webhook multi-tenant (`20251006-webhook-multi-tenant`).
- Finalizar sanitização de logs e payloads (`20251006-sanitizacao-pii`).
- Expandir conectores CRM para Salesforce após homologação do piloto.
