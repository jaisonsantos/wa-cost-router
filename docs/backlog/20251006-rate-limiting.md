---
title: "Rate limiting por organização"
type: hardening
prio: P2
estimate: "3d"
owner: "unassigned"
depends_on: []
---

> - **Status:** Concluído
> - **Caso de uso:** [UC-02 — Atendimento multicanal orquestrado](../current-cycle/USE_CASE_TRACEABILITY.md#uc-02--atendimento-multicanal-orquestrado)

## Contexto

Atualmente qualquer tenant pode saturar `POST /messages/send` ou endpoints críticos sem restrição, comprometendo estabilidade e custo. Redis já está disponível na stack e pode ser usado para contadores TTL.

## Escopo

- Implementar middleware/dependency que limite chamadas por `org_id` e endpoint (ex.: 60 req/min em `/messages/send`).
- Expor cabeçalhos `X-RateLimit-Remaining`/`Retry-After`.
- Registrar eventos de bloqueio para observabilidade.
- Permitir configuração via env (limites diferentes por rota).

## Acceptance Criteria

- Requisições excedendo o limite retornam 429 com mensagem clara.
- Limite é aplicado isoladamente por organização.
- Métricas/alertas documentados em [Operações](../operations/OPERATIONS.md).
- Coleção Postman possui teste demonstrando resposta 429 (usar script para disparar > limite em Newman).

## Subtasks

- [x] Criar helper em `app/core` para manipular contadores Redis com TTL (`backend/app/core/rate_limiter.py`).
- [x] Aplicar rate limit em `/auth/login` (proteção contra brute force) e `/messages/send` (`backend/app/api/auth.py`, `backend/app/api/messages.py`).
- [x] Escrever testes unitários cobrindo limites, reset e fallback (`backend/tests/test_messages_api.py`).
- [x] Atualizar documentação (`docs/security/SECURITY.md`, `docs/operations/OPERATIONS.md`) e demonstração Postman (`docs/postman/README.md#demonstração-de-rate-limit-429-too-many-requests`).

## Referências

- [Segurança](../security/SECURITY.md)
- [Operações](../operations/OPERATIONS.md)
- [API Messages](../api/API_REFERENCE.md)

## Out of Scope

- Quotas/medição financeira (cobrança) – tratado em backlog de pricing.
- Implementação de rate limit por usuário individual (foco inicial é org).
