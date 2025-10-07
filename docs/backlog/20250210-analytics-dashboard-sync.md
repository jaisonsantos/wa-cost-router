# 20250210 - Sincronizar dashboard de analytics (P2)

## Contexto
O dashboard atual consome eventos limitados e não reflete os dados que serão gerados após a persistência de `MessageEvent` e `CostRecord`. Precisamos alinhar o frontend aos novos contratos para garantir métricas confiáveis.

## Hipótese de valor
Ao sincronizar o dashboard com os eventos reais, stakeholders terão visibilidade precisa de custos, economia e performance, aumentando a confiança no produto.

## Escopo inicial
- Atualizar serviços/frontend para consumir os novos campos de `MessageEvent` e `CostRecord`.
- Ajustar agregações e gráficos para mostrar baseline vs. otimizado, sucesso/falha, economia.
- Criar testes de integração (React Testing Library) cobrindo renderização com dados reais.
- Garantir endpoints backend com filtros/ordenções necessários para o dashboard.
- Atualizar documentação com capturas de tela e fluxo analítico.

## Dependências
- Conclusão de T3 (persistência dos eventos) e T8 (mascaramento de PII) para manter consistência de dados.

## DoD
- `make dev` e `make ci` verdes com testes de frontend atualizados.
- Coleção Postman validando endpoints consumidos pelo dashboard.
- Documentação atualizada em [`docs/overview/README.md`](../overview/README.md) e [`docs/architecture/ARCHITECTURE.md`](../architecture/ARCHITECTURE.md).
- Registro das mudanças no roadmap em [`docs/roadmap/ROADMAP.md`](../roadmap/ROADMAP.md).
- Evidências visuais (capturas de tela) anexadas ao PR mostrando dashboard atualizado.
