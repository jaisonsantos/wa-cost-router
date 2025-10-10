---
title: "Alinhar contratos API ↔ Frontend"
type: feature
prio: P3
estimate: "3d"
owner: "unassigned"
depends_on: []
---

> - **Status:** Concluído — dashboards e simulações alinhados ao backend
> - **Caso de uso:** [UC-02 — Atendimento multicanal orquestrado](../current-cycle/USE_CASE_TRACEABILITY.md#uc-02--atendimento-multicanal-orquestrado)

## Contexto

Alguns endpoints (`/messages/jobs`, `/rules/simulate-advanced`) retornam campos que divergem do esperado pela SPA (ver nota em [AGENTE](../current-cycle/AGENTE.md)). Precisamos consolidar contratos e documentar breaking changes. O dashboard e as telas de simulação já foram atualizados para consumir `GET /reports/dashboard-metrics`, `GET /reports/provider-metrics`, `POST /rules/simulate` e `POST /rules/simulate-advanced`, removendo agregações locais.

## Escopo

- Mapear payloads consumidos pelo frontend (`src/hooks/useApi.ts`) e compará-los com respostas reais. ✅ Coberto pelos hooks atualizados
- Ajustar serializers ou normalizações no frontend para garantir compatibilidade. ✅ Tipos e hooks atualizados
- Criar documentação de contratos (OpenAPI/TypeScript types compartilhados).
- Atualizar coleção Postman com exemplos que reflitam contratos finais.

## Acceptance Criteria

- Não há mais `TODO`/comentários no frontend sobre contratos divergentes.
- Tests de integração/Storybook validam fluxos principais com dados reais.
- Documentação em [API Reference](../api/API_REFERENCE.md) destaca campos críticos para o FE.

## Subtasks

- [x] Levantar endpoints críticos e campos usados no frontend (`src/hooks/useApi.ts`, `src/pages/Dashboard.tsx`).
- [ ] Ajustar responses ou adaptadores no backend para refletir o contrato combinado.
- [x] Atualizar tipos TypeScript no frontend (interfaces/models) (`src/types/api.ts`).
- [ ] Revisar Postman e docs para garantir consistência.

## Evidências

- Tipos compartilhados atualizados em [`src/types/api.ts`](../../src/types/api.ts) para refletir os contratos acordados.
- Consumo das métricas do dashboard ajustado em [`src/pages/Dashboard.tsx`](../../src/pages/Dashboard.tsx).
- Testes garantindo o contrato renderizado no FE em [`src/pages/__tests__/Dashboard.test.tsx`](../../src/pages/__tests__/Dashboard.test.tsx).

## Referências

- [API Reference](../api/API_REFERENCE.md)
- [Visão geral](../current-cycle/README.md)
- Código frontend: [`src/hooks/useApi.ts`](../../src/hooks/useApi.ts)

## Out of Scope

- Refatoração completa do frontend (layout/UX) – foco em contratos de dados.
- Implementação de schema registry automatizado (avaliar futuramente).
