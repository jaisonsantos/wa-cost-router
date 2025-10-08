# AGENTE.md — Ciclo Atual

## Objetivo do ciclo
- Concluir o ciclo de **contatos/opt-ins multi-tenant** habilitando o piloto externo com catálogo único de contatos, registro explícito de consentimento e governança operacional alinhada às exigências de compliance.
- Endereçar os gaps críticos mapeados em [`docs/analysis/USE_CASE_GAP.md`](docs/analysis/USE_CASE_GAP.md) relacionados à ingestão e ao tratamento de dados pessoais, mantendo alinhamento com o plano vigente em [`docs/current-cycle/NEXT_IMPLEMENTATION_PLAN.md`](docs/current-cycle/NEXT_IMPLEMENTATION_PLAN.md).
- Garantir que as squads mantenham foco no valor de negócio descrito no [roadmap do ciclo atual](docs/current-cycle/README.md), priorizando as frentes marcadas como P0.

## Escopo
- Implementar o catálogo multi-tenant de contatos com capacidades de importação segura, deduplicação e enriquecimento incremental.
- Habilitar a jornada de opt-in/opt-out com rastreamento auditável, integrações com provedores WA e sincronização com conectores CRM priorizados.
- Assegurar que rotas inbound (webhook WhatsApp) e outbound respeitem consentimento ativo, isolamento por organização e sanitização de PII.
- Atualizar a documentação operacional e de compliance para refletir políticas de consentimento e os novos fluxos de governança do ciclo.
- Manter o [índice do backlog por caso de uso](docs/backlog/INDEX_BY_USE_CASE.md) alinhado à matriz de rastreabilidade, promovendo as frentes de contatos/opt-ins a prioridade P0.

## Critérios de aceite do ciclo
- Catálogo de contatos multi-tenant entregue com migração controlada, importação validada e deduplicação em produção.
- Opt-ins registrados e versionados com auditoria completa (quem, quando, origem) e expostos via API/relatórios.
- Webhook WhatsApp roteando dinamicamente por `org_id` e validando consentimento ativo antes de enviar respostas automáticas.
- Política de sanitização e retenção de PII aplicada aos novos fluxos, com playbooks operacionais atualizados.
- Backlog e roadmap atualizados com status P0 cumprido e dependências destravadas para os épicos de CRM (E3) e governança (E4).

## Entregáveis
- Incrementos funcionais descritos na seção “Próxima Milestone” do [plano de implementação](docs/current-cycle/NEXT_IMPLEMENTATION_PLAN.md).
- Documentação e playbooks atualizados de acordo com as necessidades do ciclo, seguindo o mapeamento mantido no [roadmap do ciclo](docs/current-cycle/README.md) e no [backlog priorizado](docs/current-cycle/AGENTE.md).
- Evidências de mitigação dos gaps registrados em [`docs/analysis/USE_CASE_GAP.md`](docs/analysis/USE_CASE_GAP.md).

## Checklist operacional
- [ ] Validar diariamente o progresso dos itens P0/P1 conforme o [backlog priorizado](docs/current-cycle/AGENTE.md).
- [ ] Sincronizar dependências inter-equipes usando o [plano de implementação](docs/current-cycle/NEXT_IMPLEMENTATION_PLAN.md).
- [ ] Revisar impactos de roadmap e riscos antes de cada release, consultando o [roadmap do ciclo](docs/current-cycle/README.md).
- [ ] Registrar decisões e desvios que afetem os gaps identificados em [`docs/analysis/USE_CASE_GAP.md`](docs/analysis/USE_CASE_GAP.md).

## Próxima etapa
- Executar as atividades sinalizadas como “Next Up” em [`docs/current-cycle/NEXT_IMPLEMENTATION_PLAN.md`](docs/current-cycle/NEXT_IMPLEMENTATION_PLAN.md), garantindo que cada entrega continue endereçando as lacunas listadas em [`docs/analysis/USE_CASE_GAP.md`](docs/analysis/USE_CASE_GAP.md).

## Processo de encerramento
1. Ao concluir o ciclo, mover este arquivo e os demais artefatos pertinentes para `docs/archive/<ano>-<ciclo>/`, preservando a estrutura definida em [`docs/current-cycle/README.md`](docs/current-cycle/README.md).
2. Atualizar o índice histórico com um link para o novo local, seguindo o padrão descrito no [backlog priorizado](docs/current-cycle/AGENTE.md) para documentação encerrada.
3. Referenciar, no novo local, como os gaps de [`docs/analysis/USE_CASE_GAP.md`](docs/analysis/USE_CASE_GAP.md) foram tratados e qual será o foco do próximo ciclo conforme o [plano de implementação](docs/current-cycle/NEXT_IMPLEMENTATION_PLAN.md).
