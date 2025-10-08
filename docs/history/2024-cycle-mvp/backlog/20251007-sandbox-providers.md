---
title: "Sandbox de conectores e seeds determinísticas"
type: hardening
prio: P0
estimate: "4d"
owner: "backend"
depends_on: []
---

> - **Status:** Concluído
> - **Caso de uso:** [UC-02 — Atendimento multicanal orquestrado](../../../current-cycle/USE_CASE_TRACEABILITY.md#uc-02--atendimento-multicanal-orquestrado)

## Contexto

Os conectores atuais (`Dialog360Connector`, `GupshupConnector`) realizam chamadas HTTP reais mesmo em desenvolvimento e CI. Como as credenciais de demo são fictícias, os requests retornam timeout/erro 401, atrasando a coleção Newman e impedindo que a API gere eventos/custos consistentes. Além disso, o seed usa dados aleatórios, o que dificulta comparar resultados entre execuções e validar métricas.

Precisamos de um modo sandbox para curto-circuitar integrações externas, retornando respostas fake e determinísticas enquanto mantemos o mesmo contrato da API. Isso garante que `make dev`, `make ci` e a coleção Postman completem em menos de 60s e que relatórios/roteamento tenham dados reproduzíveis.

## Escopo

- Introduzir feature toggle (`SANDBOX_PROVIDERS`) e parâmetros de latência/resposta fake carregados via settings.
- Ajustar `get_connector`/`ProviderConnector` para delegar a um conector sandbox que simule envio e health check sem sair da aplicação.
- Atualizar pipeline de envio (`messages.py`) para respeitar o sandbox, preenchendo `DeliveryAttempt`/`CostRecord` com payloads coerentes.
- Tornar o seed determinístico (sem `random`), alinhando providers, rate cards e eventos ao cenário sandbox.
- Documentar o modo sandbox em Operações/Arquitetura e expor variáveis no `.env.example`/`docker-compose`.
- Cobrir o novo fluxo com testes automatizados (pytest) garantindo que o sandbox evita chamadas HTTP reais.

## Acceptance Criteria

- Com `SANDBOX_PROVIDERS=true` a API responde sucesso para `POST /messages/send`, persiste `DeliveryAttempt` com `success=True` e gera `CostRecord` com valores > 0 sem acessar serviços externos.
- Health check (`POST /providers/{id}/health`) retorna sucesso instantâneo no sandbox.
- `make dev`/`make ci` executam em < 60s com coleção Newman verde (sem timeouts por HTTP externo).
- Seed gera sempre os mesmos providers/rates/eventos, permitindo comparar métricas entre execuções.
- Documentação (`docs/operations/OPERATIONS.md`, `docs/architecture/ARCHITECTURE.md`) explica como ativar o sandbox e suas limitações.

## Subtasks

- [x] Adicionar flags `SANDBOX_PROVIDERS`, `SANDBOX_LATENCY_MS` (default 100) e `SANDBOX_FAILURE_RATE` (default 0) em `backend/app/core/config.py`, propagar para `.env.example`, `docker-compose.yml` e citar no `Makefile`/README quando relevante.
- [x] Implementar `SandboxProviderConnector` em `backend/app/services/provider_connectors.py` (ou módulo dedicado) que respeite as flags de latência/falha, gere `provider_message_id` fake e respostas determinísticas para `send_message`/`health_check`.
- [x] Atualizar `get_connector`/rotas (`backend/app/api/messages.py`, `backend/app/api/providers.py`) para usar o conector sandbox quando o toggle estiver ativo, garantindo que `DeliveryAttempt` e `CostRecord` sejam gravados com dados coerentes (incluindo `latency_ms` configurável e `provider_response` fake).
- [x] Refatorar `backend/scripts/seed.py` (e demais seeds relacionados) para remover uso de `random`, alinhar credenciais fake às expectativas do sandbox e garantir dados consistentes para relatórios/routing.
- [x] Criar/atualizar testes pytest cobrindo o fluxo sandbox (`backend/tests`) validando que nenhuma chamada HTTP externa é realizada e que os registros persistidos correspondem aos valores simulados.
- [x] Atualizar documentação (`docs/operations/OPERATIONS.md`, `docs/architecture/ARCHITECTURE.md`, `docs/current-cycle/README.md` se aplicável) descrevendo o modo sandbox, novas variáveis de ambiente e impacto na execução da stack/local CI.
- [x] Revisar coleção Postman (`docs/postman/wa-cost-router.postman_collection.json`) e README para garantir que os cenários utilizam o sandbox/credenciais seed e executar `make ci` para validar.

## Referências

- [Plano de Próxima Etapa](../../../current-cycle/NEXT_IMPLEMENTATION_PLAN.md)
- [Arquitetura](../../../architecture/ARCHITECTURE.md)
- [Operações](../../../operations/OPERATIONS.md)
- [Seeds](../../../../backend/scripts/seed.py)
- [API Messages](../../../api/API_REFERENCE.md)

## Out of Scope

- Mover o envio para worker assíncrono (coberto pelo card `20250210-worker-offload`).
- Configurações avançadas de falha por provedor (percentual específico por connector) – iniciar com parâmetros globais.
