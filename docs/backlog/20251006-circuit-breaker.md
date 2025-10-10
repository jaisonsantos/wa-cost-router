---
title: "Circuit breaker por provedor"
type: resilience
prio: P2
estimate: "4d"
owner: "unassigned"
depends_on: ["20251006-rate-limiting"]
---

> - **Status:** Concluído
> - **Caso de uso:** [UC-02 — Atendimento multicanal orquestrado](../current-cycle/USE_CASE_TRACEABILITY.md#uc-02--atendimento-multicanal-orquestrado)

## Contexto

Falhas consecutivas de um provedor (ex.: 360dialog) podem degradar a fila inteira, pois o motor tenta enviar repetidamente. Precisamos de um circuito que abra após N erros e utilize fallback automaticamente.

## Escopo

- Implementar circuito por `provider_id` com contadores em Redis (estado `closed`/`open`/`half-open`).
- Integrar com `RoutingEngine` para ignorar provedores em estado `open` e usar fallback chain.
- Expor métricas (quantidade de circuitos abertos) para Prometheus.
- Adicionar alertas em caso de circuito aberto por mais de X minutos.

## Acceptance Criteria

- Após X erros consecutivos configuráveis, novas tentativas usam fallback ou retornam erro claro.
- Circuito fecha automaticamente após período de cooldown e tentativa bem sucedida.
- Métricas disponíveis em `/admin/metrics` e documentação atualizada.
- Testes automatizados cobrindo abertura, meia-abertura e fechamento do circuito.

## Subtasks

- [x] Definir thresholds/configuração via env (`CIRCUIT_BREAKER_THRESHOLD`, `CIRCUIT_BREAKER_COOLDOWN_SECONDS`) e documentar operação (`docs/operations/OPERATIONS.md`).
- [x] Persistir estado no Redis (estrutura chave `circuit:{provider_id}`) através de `CircuitBreakerStore` (`backend/app/core/circuit_breaker.py`).
- [x] Atualizar `RoutingEngine`/delivery para consultar estado antes de escolher provedor (`backend/app/api/messages.py`).
- [x] Adicionar logs e métricas (`messages_circuit_breaker_state`, `messages_delivery_attempts_total`) em `backend/app/api/messages.py`.
- [x] Atualizar [Postman](../postman/README.md#demonstração-de-circuit-breaker-rota-com-fallback) com instruções para simular fallback.

## Referências

- [Arquitetura](../architecture/ARCHITECTURE.md)
- [Operações](../operations/OPERATIONS.md)
- [API Messages](../api/API_REFERENCE.md)

## Out of Scope

- Implementar retry/backoff configurável por provedor (avaliar posteriormente).
- Circuit breaker separado para integrações externas (ex.: webhook ingestion).
