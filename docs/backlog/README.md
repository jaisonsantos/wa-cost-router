[Docs](../current-cycle/README.md) › [Backlog](./README.md)
# Backlog Prioritário

Os itens abaixo seguem o formato `YYYYMMDD-<slug>.md` com frontmatter contendo tipo, prioridade (**P0 crítico imediato → P3 baixo**), estimativa e dependências. Cada card detalha contexto, escopo, critérios de aceite, subtarefas e referências cruzadas para documentação e endpoints relevantes. Consulte o [índice por caso de uso](./INDEX_BY_USE_CASE.md) para navegar rapidamente pelos cards alinhados à matriz do ciclo.

## Processo de priorização orientado pela matriz de casos de uso

1. Comece pela [matriz de rastreabilidade](../current-cycle/USE_CASE_TRACEABILITY.md) para identificar o caso de uso impactado e entender dependências vigentes.
2. Atualize o card correspondente com o status atual (**Pendente**, **Em andamento** ou **Concluído**) e mantenha um link explícito para o caso de uso escolhido, garantindo rastreabilidade bidirecional.
3. Reavalie prioridades considerando o efeito do item na matriz (bloqueios críticos → UC-01/UC-02, governança comercial → UC-04, etc.) e sincronize com o [plano de implementação](../current-cycle/NEXT_IMPLEMENTATION_PLAN.md).
4. Sempre que um card mudar para **Concluído** ou se tornar obsoleto, mova-o para `docs/history/2024-cycle-mvp/backlog/` com uma nota de encerramento, mantendo o backlog atual focado em entregas ativas.

## Como usar

1. Ler o README da tarefa para entender objetivo e contexto histórico.
2. Validar dependências antes de puxar um item (ex.: migrations ou integrações).
3. Atualizar subtarefas com owners/parciais conforme o trabalho avança.
4. Sempre linkar PRs/tickets que enderecem o item para manter rastreabilidade.

Status disponíveis:

- **Pendente** – Card ainda não iniciado ou aguardando desbloqueio.
- **Em andamento** – Implementação ativa com subtarefas em progresso.
- **Concluído** – Escopo entregue; documentação e links atualizados.

Prioridades atuais:

- **P0** – Frentes de contatos/opt-ins multi-tenant (catálogo, timeline, consentimento, sanitização e webhook WA). Devem ser acompanhadas diariamente e liberam a etapa de piloto externo.
- **P1** – Bloqueadores para go-live externo restantes (proteção de métricas, enforcement de secrets, compliance residual).
- **P2** – Resiliência e governança (rate limiting, circuit breaker, validações).
- **P3** – Otimizações futuras e acordos com frontend.

## Veja também

- [Visão geral](../current-cycle/README.md)
- [Segurança](../security/SECURITY.md)
- [Roadmap](../roadmap/ROADMAP.md)
