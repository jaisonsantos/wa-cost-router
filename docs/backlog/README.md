[Docs](../overview/README.md) › [Backlog](./README.md)
# Backlog Prioritário

Os itens abaixo seguem o formato `YYYYMMDD-<slug>.md` com frontmatter contendo tipo, prioridade (P1 crítico → P3 baixo), estimativa e dependências. Cada card detalha contexto, escopo, critérios de aceite, subtarefas e referências cruzadas para documentação e endpoints relevantes.

## Como usar

1. Ler o README da tarefa para entender objetivo e contexto histórico.
2. Validar dependências antes de puxar um item (ex.: migrations ou integrações).
3. Atualizar subtarefas com owners/parciais conforme o trabalho avança.
4. Sempre linkar PRs/tickets que enderecem o item para manter rastreabilidade.

Prioridades atuais:

- **P1** – Bloqueadores para go-live externo (segurança multi-tenant, PII, métricas sensíveis, secret enforcement).
- **P2** – Resiliência e governança (rate limiting, circuit breaker, validações).
- **P3** – Otimizações futuras e acordos com frontend.

## Veja também

- [Visão geral](../overview/README.md)
- [Segurança](../security/SECURITY.md)
- [Roadmap](../roadmap/ROADMAP.md)
