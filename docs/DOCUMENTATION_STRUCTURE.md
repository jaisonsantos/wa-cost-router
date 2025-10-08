# Estrutura de Documentação

- **Data da proposta**: 2025-10-08
- **Autor**: Agente Automatizado (GPT-5 Codex)

## 1. Revisão do material existente

- O arquivo solicitado `docs/analysis/USE_CASE_GAP.md` não está presente no repositório atual. Recomenda-se restaurá-lo ou recriá-lo sob a nova taxonomia (ver seção [Referências transversais](#43-referências-transversais)) para consolidar análises de lacunas de uso.
- Foram inventariados os diretórios ativos `docs/current-cycle`, `docs/archive` e `docs/backlog`, listados na seção seguinte com links navegáveis.

## 2. Inventário dos diretórios principais

| Diretório | Propósito atual | Conteúdos chave |
|-----------|-----------------|-----------------|
| [`docs/current-cycle/`](current-cycle/README.md) | Porta de entrada para o ciclo ativo, com visão geral, plano de próximas implementações e sumário executivo técnico. | [`Ciclo Atual`](current-cycle/README.md), [`NEXT_IMPLEMENTATION_PLAN`](current-cycle/NEXT_IMPLEMENTATION_PLAN.md), [`AGENTE`](current-cycle/AGENTE.md) |
| [`docs/archive/`](archive/) | Histórico consolidado das fases anteriores do produto, incluindo status do MVP, checklist de segurança e log de iterações. | [`ITERATION_LOG`](archive/ITERATION_LOG.md), [`MVP_IMPLEMENTATION_STATUS`](archive/MVP_IMPLEMENTATION_STATUS.md), [`MVP_FINAL_STATUS`](archive/MVP_FINAL_STATUS.md), [`MVP_SECURITY_CHECKLIST`](archive/MVP_SECURITY_CHECKLIST.md), [`IMPLEMENTATION_STATUS`](archive/IMPLEMENTATION_STATUS.md), [`MVP_PLANNING`](archive/MVP_PLANNING.md), [`BACKEND_README`](archive/BACKEND_README.md), [`CHANGELOG`](archive/CHANGELOG.md) |
| [`docs/backlog/`](backlog/README.md) | Pipeline priorizado de iniciativas futuras, organizado por arquivos `YYYYMMDD-slug.md` com contexto, critérios e dependências. | [`README`](backlog/README.md) e cards como [`20251006-contratos-api-fe`](backlog/20251006-contratos-api-fe.md), [`20251006-sanitizacao-pii`](backlog/20251006-sanitizacao-pii.md), [`20251006-webhook-multi-tenant`](backlog/20251006-webhook-multi-tenant.md), [`20250210-rate-card-multitenant`](backlog/20250210-rate-card-multitenant.md) |

## 3. Referência rápida de seções existentes

- [Ciclo Atual](current-cycle/README.md)
- [Plano da Próxima Iteração](current-cycle/NEXT_IMPLEMENTATION_PLAN.md)
- [Relatório do Agente Técnico](current-cycle/AGENTE.md)
- [Log de Iterações](archive/ITERATION_LOG.md)
- [Status do MVP](archive/MVP_IMPLEMENTATION_STATUS.md)
- [Checklist de Segurança do MVP](archive/MVP_SECURITY_CHECKLIST.md)
- [Planejamento do MVP](archive/MVP_PLANNING.md)
- [Changelog histórico](archive/CHANGELOG.md)
- [Backlog Prioritário](backlog/README.md)
- [Cards do Backlog](backlog/)

## 4. Taxonomia proposta

### 4.1 Ciclo atual

- **Objetivo**: Centralizar o que está em execução ou pronto para entrega imediata.
- **Localização recomendada**: `docs/current-cycle/`.
- **Conteúdos típicos**:
  - Visão geral do produto, instruções de quick start e estrutura (ex.: [`current-cycle/README.md`](current-cycle/README.md)).
  - Plano da sprint/iteração corrente (ex.: [`current-cycle/NEXT_IMPLEMENTATION_PLAN.md`](current-cycle/NEXT_IMPLEMENTATION_PLAN.md)).
  - Relatórios executivos/técnicos vigentes (ex.: [`current-cycle/AGENTE.md`](current-cycle/AGENTE.md)).
- **Boas práticas**:
  - Atualizar sempre que o foco do time mudar.
  - Referenciar diretamente tarefas do backlog ativas para facilitar o rastreamento.

### 4.2 Histórico por iteração

- **Objetivo**: Preservar contexto passado, decisões e aprendizados concluídos.
- **Localização recomendada**: `docs/archive/`.
- **Conteúdos típicos**:
  - Logs de iteração com resumo do que foi entregue e próximos passos concluídos (ex.: [`archive/ITERATION_LOG.md`](archive/ITERATION_LOG.md)).
  - Estados consolidados do MVP e checklists de auditoria (ex.: [`archive/MVP_IMPLEMENTATION_STATUS.md`](archive/MVP_IMPLEMENTATION_STATUS.md), [`archive/MVP_SECURITY_CHECKLIST.md`](archive/MVP_SECURITY_CHECKLIST.md)).
  - Documentos históricos de planejamento e mudanças (ex.: [`archive/MVP_PLANNING.md`](archive/MVP_PLANNING.md), [`archive/CHANGELOG.md`](archive/CHANGELOG.md)).
- **Boas práticas**:
  - Mover para o arquivo histórico correspondente assim que um ciclo for fechado.
  - Manter índice cronológico para facilitar consultas retroativas.

### 4.3 Referências transversais

- **Objetivo**: Reunir materiais que dão suporte contínuo a múltiplos ciclos (APIs, arquitetura, segurança, análises de gaps, runbooks).
- **Localização recomendada**: diretórios temáticos sob `docs/` (ex.: `api/`, `architecture/`, `operations/`, `security/`, `pricing/`, `postman/`) e um novo subdiretório `docs/analysis/` para estudos de lacunas como `USE_CASE_GAP.md`.
- **Conteúdos típicos**:
  - Guias de arquitetura e modelagem (ex.: [`architecture/ARCHITECTURE.md`](architecture/ARCHITECTURE.md), [`architecture/DATA_MODEL.md`](architecture/DATA_MODEL.md)).
  - Referência de API e coleções de teste (ex.: [`api/API_REFERENCE.md`](api/API_REFERENCE.md), [`postman/README.md`](postman/README.md)).
  - Procedimentos operacionais e de segurança (ex.: [`operations/OPERATIONS.md`](operations/OPERATIONS.md), [`security/SECURITY.md`](security/SECURITY.md)).
  - Estudos analíticos e avaliações de lacunas (ex.: reintroduzir `analysis/USE_CASE_GAP.md` com lições e oportunidades; novos relatórios seguem o mesmo diretório).
- **Boas práticas**:
- Usar links cruzados para apontar de cada análise para backlog e ciclo atual quando surgirem ações.
  - Garantir versionamento explícito quando uma referência servir de base para políticas/processos.

## 5. Próximos passos sugeridos

1. Criar `docs/analysis/USE_CASE_GAP.md` (ou restaurá-lo) dentro do novo diretório `analysis/`, seguindo o padrão de metadados utilizado neste documento.
2. Atualizar `current-cycle/NEXT_IMPLEMENTATION_PLAN.md` com referências diretas aos cards do backlog conforme a taxonomia.
3. Incluir esta estrutura no checklist de contribuição (ex.: `docs/CONTRIBUTING.md`) para reforçar onde cada artefato deve residir.

---

> _Esta proposta visa facilitar a navegação e governança da documentação, reduzindo duplicidade e melhorando a rastreabilidade entre planejamento, execução e histórico._
