# 20250210 - Offload de envios para worker RQ (P2)

## Contexto
Após a criação do sandbox, o envio de mensagens ainda ocorre inline na API. Para suportar maior volume e evitar bloqueio da thread principal, precisamos mover o processamento para um worker dedicado usando RQ (ou equivalente) mantendo compatibilidade com o fluxo atual.

## Hipótese de valor
Ao colocar os envios em uma fila dedicada, reduzimos latência percebida pelo cliente, habilitamos paralelismo controlado e criamos base para autoescalabilidade.

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
