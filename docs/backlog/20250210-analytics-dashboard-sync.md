# 20250210 - Sincronizar dashboard de analytics (P2)

> - **Status:** Em andamento — métricas e simulações integradas ao backend
> - **Caso de uso:** [UC-02 — Atendimento multicanal orquestrado](../current-cycle/USE_CASE_TRACEABILITY.md#uc-02--atendimento-multicanal-orquestrado)

## Contexto
O dashboard atual consome eventos limitados e não reflete os dados que serão gerados após a persistência de `MessageEvent` e `CostRecord`. Precisamos alinhar o frontend aos novos contratos para garantir métricas confiáveis. A tela já passou a consumir `GET /reports/dashboard-metrics`/`provider-metrics` e a apresentar recomendações do backend, enquanto a página de regras utiliza as simulações reais (`POST /rules/simulate`, `POST /rules/simulate-advanced`).

## Hipótese de valor
Ao sincronizar o dashboard com os eventos reais, stakeholders terão visibilidade precisa de custos, economia e performance, aumentando a confiança no produto.

## Escopo inicial
- Atualizar serviços/frontend para consumir os novos campos de `MessageEvent` e `CostRecord`. ✅ Dashboard sincronizado
- Ajustar agregações e gráficos para mostrar baseline vs. otimizado, sucesso/falha, economia. ✅ Indicadores e alertas ativos
- Criar testes de integração (React Testing Library) cobrindo renderização com dados reais. ✅ Cobertura adicionada (`src/pages/__tests__/`)
- Garantir endpoints backend com filtros/ordenções necessários para o dashboard.
- Atualizar documentação com capturas de tela e fluxo analítico.

## Dependências
- Conclusão de T3 (persistência dos eventos) e T8 (mascaramento de PII) para manter consistência de dados.

## DoD
- `make dev` e `make ci` verdes com testes de frontend atualizados.
- Coleção Postman validando endpoints consumidos pelo dashboard.
- Documentação atualizada em [`docs/current-cycle/README.md`](../current-cycle/README.md) e [`docs/architecture/ARCHITECTURE.md`](../architecture/ARCHITECTURE.md).
- Registro das mudanças no roadmap em [`docs/roadmap/ROADMAP.md`](../roadmap/ROADMAP.md).
- Evidências visuais (capturas de tela) anexadas ao PR mostrando dashboard atualizado.

## Evidências

- Capturas de tela de referência podem ser regeneradas com `node scripts/capture-screenshots.mjs`,
  que salva as imagens em `artifacts/screenshots/` (diretório ignorado pelo Git) para anexos externos.
