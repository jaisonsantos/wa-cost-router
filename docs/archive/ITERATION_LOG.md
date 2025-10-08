# Iteration Log

Este documento acompanha a evolução incremental das entregas. Cada entrada registra o que foi concluído, qual é a tarefa em andamento (**current**) e a próxima prioridade planejada.

## Histórico

| Data       | Tipo       | Descrição |
|------------|------------|-----------|
| 2025-10-06 | baseline   | Base documental do MVP consolidada (estado descrito em [`MVP_IMPLEMENTATION_STATUS.md`](../history/2024-cycle-mvp/MVP_IMPLEMENTATION_STATUS.md)). |
| 2025-10-06 | completed  | Builder visual de regras entregue no frontend, alinhando contratos da API e adicionando formulário completo de criação/edição. |
| 2025-10-07 | completed  | Padronizado fluxo local com novo Makefile, revisão de runbooks e README para iniciar stack rapidamente. |
| 2025-10-07 | fix        | Corrigido bootstrap local adicionando pacote Python explícito e removendo `version` obsoleto do `docker-compose.yml`. |

## Estado Atual

- **current**: Implementar export CSV funcional em Reports (`/reports`) com geração e download dos agregados (ver [`IMPLEMENTATION_STATUS.md`](../history/2024-cycle-mvp/IMPLEMENTATION_STATUS.md)).
- **next**: Iniciar automação de alertas/circuit breaker para provedores (monitorar outages e fallback automático) conforme backlog de prioridade alta.
- **backlog**: RBAC completo, API keys/webhooks e melhorias de observabilidade permanecem na fila pós-export.

## Notas

- Sempre que uma nova etapa for concluída, adicionar uma linha ao histórico e atualizar as seções *current* e *next*.
- As prioridades são derivadas dos artefatos [`IMPLEMENTATION_STATUS.md`](../history/2024-cycle-mvp/IMPLEMENTATION_STATUS.md), [`MVP_IMPLEMENTATION_STATUS.md`](../history/2024-cycle-mvp/MVP_IMPLEMENTATION_STATUS.md) e `docs/ROADMAP.md`.
- Runbooks (`docs/OPERATIONS.md`) e README refletem o fluxo atualizado via Makefile.
