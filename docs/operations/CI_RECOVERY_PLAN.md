[Docs](../current-cycle/README.md) › [Operações](./OPERATIONS.md) › Pipeline CI
# Plano de Correção – Pipeline CI bloqueada por billing

## 1. Objetivo

Restaurar a execução automática dos workflows GitHub Actions (`ci.yml`) após o bloqueio por pendências de cobrança, assegurando rastreabilidade das ações, mitigação temporária para PRs críticos e controles preventivos para evitar recorrência.

## 2. Resumo do problema

- Mensagem no GitHub Actions: `The job was not started because recent account payments have failed or your spending limit needs to be increased.`
- Impacto: nenhum workflow inicia; merges ficam bloqueados por falta de validação automatizada.
- Estado atual: mitigação provisória disponível via `make ci-lite`, mas sem plano consolidado para desbloqueio definitivo e prevenção.

## 3. Equipe e responsáveis

| Papel | Responsável | Ações chave |
| --- | --- | --- |
| Owner financeiro GitHub | `finance@empresa.com` | Regularizar pagamento, anexar comprovantes.
| Engenheiro de Release | `ops@empresa.com` | Coordenar mitigação (`ci-lite`), consolidar evidências e reexecutar workflows.
| Engenharia de Confiabilidade | `sre@empresa.com` | Revisar limites de gasto, configurar alertas e acompanhar métricas.

## 4. Linha do tempo proposta

1. **0h – Diagnóstico e comunicação**
   - Confirmar bloqueio na aba *Actions* e capturar screenshot do erro.
   - Notificar canais `#eng-prod` e `#finance` anexando o link do workflow bloqueado.
2. **+1h – Coleta de dados de billing**
   - Acessar `Settings › Billing & plans` (usuário/organização) e exportar histórico de cobranças.
   - Identificar invoices vencidas ou spending limit zerado; registrar IDs no ticket operacional.
3. **+2h – Mitigação técnica**
   - Executar `make ci-lite` para cada PR crítico; armazenar resultados em `artifacts/ci-lite/` e anexar ao PR/ticket.
   - Se necessário, complementar com `make postman-test` ou testes específicos solicitados pelo revisor.
4. **+4h – Regularização financeira**
   - Atualizar método de pagamento ou efetuar quitação manual da fatura.
   - Ajustar spending limit com margem ≥20% do consumo médio mensal.
   - Solicitar confirmação por escrito do financeiro.
5. **+5h – Revalidação na plataforma**
   - Verificar se o painel exibe `All workflows enabled`.
   - Reexecutar workflow mais recente (`Re-run jobs`) e monitorar até a conclusão.
6. **+6h – Follow-up e documentação**
   - Atualizar `docs/runbooks/ci_billing.md` com lições aprendidas (se necessário).
   - Registrar na retrospectiva do incidente (Confluence/Notion) e anexar recibos ao ticket.
   - Enviar resumo no canal `#eng-prod` com status e próximo ciclo de monitoramento.

## 5. Critérios de aceite

- [ ] Workflow `ci.yml` executa automaticamente em `push`/`pull_request` sem bloqueios administrativos.
- [ ] Todos os PRs impactados possuem relatório `ci-lite` anexado durante o período de indisponibilidade.
- [ ] Evidência do pagamento/ajuste de spending limit arquivada no ticket operacional.
- [ ] Alertas preventivos e lembretes trimestrais configurados (seção 6).

## 6. Contramedidas preventivas

1. **Alertas financeiros**
   - Habilitar notificações por e-mail para faturas e limite de gasto (Settings › Billing).
   - Configurar lembrete mensal no calendário do time financeiro para revisar consumo do Actions.
2. **Monitoramento de consumo**
   - Exportar relatório mensal de minutos/armazenamento e anexar ao dashboard operacional.
   - Adotar `github-actions-billing` como métrica no observability stack (quando disponível).
3. **Runbooks e automações**
   - Garantir que `docs/runbooks/ci_billing.md` permaneça atualizado com contatos e acesso.
   - Avaliar automatização para rodar `make ci-lite` em self-hosted runner enquanto o bloqueio persistir.

## 7. Checklist de comunicação

- [ ] Abrir ticket interno (`OPS-XXX`) com descrição do incidente, timestamps e responsáveis.
- [ ] Atualizar o ticket conforme cada etapa (diagnóstico, pagamento, verificação, fechamento).
- [ ] Comunicar stakeholders (produto, engenharia, suporte) a cada mudança de status.

## 8. Referências

- [Runbook – Desbloqueio do GitHub Actions](../runbooks/ci_billing.md)
- [Guia Operacional da Pipeline CI](./CI.md)
- [Script de mitigação local (`ci_lite`)](../../scripts/ci_lite.py)
