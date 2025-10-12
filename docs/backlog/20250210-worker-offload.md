# 20250210 - Offload de envios para worker RQ (P2)

> - **Status:** Concluído
> - **Caso de uso:** [UC-03 — CRM e jornada integrada](../current-cycle/USE_CASE_TRACEABILITY.md#uc-03--crm-e-jornada-integrada)

## Contexto
Após a criação do sandbox, o envio de mensagens ainda ocorre inline na API. Para suportar maior volume e evitar bloqueio da thread principal, precisamos mover o processamento para um worker dedicado usando RQ (ou equivalente) mantendo compatibilidade com o fluxo atual.

## Hipótese de valor
Ao colocar os envios em uma fila dedicada, reduzimos latência percebida pelo cliente, habilitamos paralelismo controlado e criamos base para autoescalabilidade.

## Resultado
- `/messages/send` agora enfileira jobs na fila `message_send`, responde `202 Accepted` com `job_id` e mantém idempotência via consulta ao banco.
- O worker dedicado (`app/workers/message_send.py`) consome a fila, invoca `MessageDeliveryService` reutilizável e atualiza métricas Prometheus (`messages_send_total`, `messages_delivery_attempts_total`, `messages_circuit_breaker_state`).
- Testes automatizados simulam a execução síncrona do worker garantindo que métricas e entidades (`MessageJob`, `DeliveryAttempt`, `MessageEvent`) sejam persistidas corretamente.
- Documentação operacional e coleção Postman foram atualizadas para refletir o novo comportamento assíncrono e orientar o acompanhamento dos jobs.

## Escopo inicial
- Criar fila `message_send` com payload estruturado (org, provider, mensagem, metadados de custo).
- Ajustar `/messages/send` para responder `202 Accepted` após enfileirar.
- Implementar worker RQ com retry exponencial e logs estruturados.
- Atualizar seeds e sandbox para publicar jobs coerentes.
- Integrar monitoração (Prometheus + logs) das filas.

## Dependências
- Conclusão do épico E1 (custos confiáveis) e T2 (sandbox) para garantir dados consistentes.

## DoD
- `make dev` e `make ci` verdes com worker habilitado.
- Coleção Postman com novo passo de verificação assíncrona (aguardando job completar).
- Documentação atualizada em [`docs/operations/OPERATIONS.md`](../operations/OPERATIONS.md) e [`docs/current-cycle/README.md`](../current-cycle/README.md).
- Guia de deploy com instruções para escalar workers em [`docs/operations/DEPLOYMENT.md`](../operations/DEPLOYMENT.md).
- Evidências (logs/prints) anexadas ao PR mostrando job processado e métricas expostas.
