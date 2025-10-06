---
title: "Rate limiting por organização"
type: hardening
prio: P2
estimate: "3d"
owner: "unassigned"
depends_on: []
---

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

- [ ] Criar helper em `app/core` para manipular contadores Redis com TTL.
- [ ] Aplicar rate limit em `/auth/login` (proteção contra brute force) e `/messages/send`.
- [ ] Escrever testes unitários cobrindo limites, reset e fallback.
- [ ] Atualizar documentação (`docs/security/SECURITY.md`) com política de rate limit.

## Referências

- [Segurança](../security/SECURITY.md)
- [Operações](../operations/OPERATIONS.md)
- [API Messages](../api/API_REFERENCE.md)

## Out of Scope

- Quotas/medição financeira (cobrança) – tratado em backlog de pricing.
- Implementação de rate limit por usuário individual (foco inicial é org).
