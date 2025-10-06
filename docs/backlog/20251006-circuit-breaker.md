---
title: "Circuit breaker por provedor"
type: resilience
prio: P2
estimate: "4d"
owner: "unassigned"
depends_on: ["20251006-rate-limiting"]
---

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

- [ ] Definir thresholds/configuração via env (`CIRCUIT_BREAKER_THRESHOLD`, `CIRCUIT_BREAKER_COOLDOWN`).
- [ ] Persistir estado no Redis (estrutura chave `circuit:{provider_id}`).
- [ ] Atualizar `RoutingEngine.select_provider` para consultar estado antes de escolher provedor.
- [ ] Adicionar logs e métricas (`Counter`/`Gauge`) em `backend/app/api/messages.py`.
- [ ] Atualizar [Postman](../postman/README.md) com instruções para simular fallback.

## Referências

- [Arquitetura](../architecture/ARCHITECTURE.md)
- [Operações](../operations/OPERATIONS.md)
- [API Messages](../api/API_REFERENCE.md)

## Out of Scope

- Implementar retry/backoff configurável por provedor (avaliar posteriormente).
- Circuit breaker separado para integrações externas (ex.: webhook ingestion).
