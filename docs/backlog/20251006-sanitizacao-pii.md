---
title: "Sanitização de PII e logs sensíveis"
type: hardening
prio: P1
estimate: "2d"
owner: "unassigned"
depends_on: []
---

> - **Status:** Pendente
> - **Caso de uso:** [UC-01 — Gestão de contatos unificada](../current-cycle/USE_CASE_TRACEABILITY.md#uc-01--gest%C3%A3o-de-contatos-unificada)

## Contexto

Campos como `MessageJob.variables` e `DeliveryAttempt.provider_response` armazenam payloads brutos dos provedores, incluindo números de telefone e mensagens. Logs e respostas da API podem expor essas informações violando requisitos LGPD.

## Escopo

- Implementar mascaramento/anonimização nos modelos persistidos (`variables`, `provider_response`) antes de salvar ou ao serializar.
- Introduzir utilitário central de logging seguro para remover PII de traces (`app.core`).
- Atualizar responses do backend para não expor dados sensíveis (ex.: ocultar números completos em `/messages/jobs`).
- Garantir que a coleção Postman e documentação reflitam os campos mascarados.

## Acceptance Criteria

- Auditoria confirma que nenhum endpoint retorna número completo ou tokens de provedores.
- Logs de envio/erro exibem identificadores anônimos (hash/últimos dígitos).
- Documentação de [Segurança](../security/SECURITY.md) atualizada com estratégia de mascaramento.

## Subtasks

- [ ] Criar helper `mask_phone(number: str)` com testes unitários.
- [ ] Atualizar serializers/responses em [`backend/app/api/messages.py`](../../backend/app/api/messages.py).
- [ ] Revisar `DeliveryAttempt` e `MessageEvent` para armazenar apenas dados essenciais.
- [ ] Adicionar teste de integração (Pytest) garantindo que `/messages/jobs` e `/messages/jobs/{id}` retornem dados mascarados.
- [ ] Atualizar Postman assertions para validar formato mascarado.
- [ ] Documentar política de retenção/mascaramento em `docs/security/SECURITY.md`.

## Referências

- [Segurança](../security/SECURITY.md)
- [Modelagem de dados](../architecture/DATA_MODEL.md)
- [API Messages](../api/API_REFERENCE.md)

## Out of Scope

- Pseudonimização completa de payloads históricos (será tratada em migração separada).
- Revisão de dados armazenados em data warehouse externo.
