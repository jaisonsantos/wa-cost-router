[Docs](../current-cycle/README.md) › [Runbooks](./) › CI Billing
# Runbook – Desbloqueio do GitHub Actions por pendências de cobrança

## Contexto

Quando o GitHub bloqueia os workflows com a mensagem `The job was not started because recent account payments have failed or your spending limit needs to be increased`, nenhum job de CI inicia. Este runbook descreve o processo para regularizar o billing e comprovar que a CI voltou a funcionar.

## Pré-requisitos

- Acesso administrativo ao repositório/organização no GitHub.
- Acesso ao método de pagamento cadastrado ou a alguém do financeiro capaz de regularizar.
- Permissão para reexecutar workflows (`Actions: read & re-run`).

## Procedimento de desbloqueio

1. **Confirmar o bloqueio:**
   - Abra a aba *Actions* do repositório e tente reexecutar qualquer workflow.
   - Se a execução falhar imediatamente com a mensagem de erro acima, prossiga para o passo 2.
2. **Verificar faturas pendentes:**
   - Acesse `https://github.com/settings/billing` (usuário) ou `https://github.com/organizations/<org>/settings/billing` (organização).
   - Revise a seção *Recent payments* e *Spending limit*. Clique em **View payment history** para identificar cobranças recusadas.
3. **Regularizar pagamento:**
   - Atualize o cartão/forma de pagamento ou quite a fatura pendente pelo botão **Pay invoice**.
   - Caso o spending limit esteja zerado, ajuste o valor conforme a projeção de minutos/armazenamento necessária para o mês.
4. **Mitigação temporária (enquanto o bloqueio persiste):**
   - Execute `make ci-lite` para rodar lint/build/testes sem Docker. O comando gera logs e `artifacts/ci-lite/summary.json` com o status de cada etapa.
   - Anexe o relatório ao PR/ticket impactado como evidência de validação manual até que o Actions volte a processar jobs.
   - Se algum passo falhar localmente, trate a correção na branch antes de retentar o fluxo no GitHub.
5. **Confirmar reativação:**
   - Na mesma tela de Billing, certifique-se de que a caixa *Actions* exibe o status **All workflows enabled**.
   - Retorne à aba *Actions* do repositório e clique em **Re-run jobs** (ou dispare `workflow_dispatch`) para o workflow bloqueado.
6. **Registrar evidências:**
   - Salve o recibo/ID da transação e registre no canal de operações ou na ferramenta de ITSM conforme política interna.
   - Atualize o ticket operacional ligado à tarefa `Regularizar billing do GitHub Actions` com data/hora e responsável.

## Validação pós-desbloqueio

- Verifique se os jobs `backend`, `frontend` e `e2e` aparecem como `queued` e executam normalmente.
- Enquanto não houver confirmação oficial, rode `make ci-lite` localmente e anexe o relatório ao PR para cobrir o período em que o Actions esteve indisponível.
- Após a liberação, retome `make ci` (ou reexecuções no Actions) para validar a pipeline completa.
- Se o bloqueio persistir após regularização, abra chamado com o GitHub em `https://support.github.com/` anexando o ID da fatura quitada.

## Notas

- O bloqueio de billing impacta toda a organização; coordene com outras squads para evitar gargalos de merge.
- Mantenha o spending limit com margem mínima de 20% sobre o consumo médio mensal para prevenir novos bloqueios.
- Registre lições aprendidas no relatório mensal de operações.
