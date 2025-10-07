[Docs](../overview/README.md) › [Postman](./README.md)
# Coleção Postman

A coleção `WA Cost Router` cobre 100% dos endpoints do backend com variáveis encadeadas para um fluxo E2E completo.

## Estrutura

1. **Auth** – registra usuário aleatório (`postman+timestamp`) com senha forte gerada no runtime e efetua login (token salvo automaticamente).
2. **Organization** – obtém `org_id` via `/orgs/current`.
3. **Providers** – cria provedor WhatsApp (360dialog), salva credenciais fake e executa health check.
4. **Rules** – lista, cria, atualiza e alterna regras, incluindo simulação avançada.
5. **Messages** – envia mensagem, lista jobs e consulta detalhes do job usando `job_id` capturado.
6. **Rates** – consulta tarifas e importa CSV de exemplo (`docs/postman/sample_rates.csv`) já preenchendo `provider_id` com o provedor criado na etapa Providers.
7. **Reports** – consome métricas de dashboard, resumo e métricas por provedor.
8. **Integrations** – cria conexão WA, valida webhook (`hub.verify_token`) e envia payload de webhook (repetir a criação com o mesmo `phone_id` apenas atualiza o registro).
9. **Admin** – checa `/admin/health` e `/admin/metrics`.
10. **Cleanup** – remove credenciais do provedor criado durante o fluxo.

Scripts de coleção adicionam o header `Authorization` automaticamente sempre que `token` estiver definido e validam que todas as respostas retornem status 2xx.

## Variáveis de ambiente

Arquivo: [`wa-cost-router.postman_environment.json`](./wa-cost-router.postman_environment.json)

| Variável | Descrição |
|----------|-----------|
| `base_url` | URL base da API (default `http://localhost:8000`). |
| `email` / `password` | Credenciais seed (`admin@demo.local` / `demo123`) usadas como fallback até o prerequest gerar valores fortes por execução. |
| `token` | JWT salvo pelos testes (não preencha manualmente). |
| `org_id`, `provider_id`, `rule_id`, `job_id` | IDs capturados automaticamente para uso em chamadas subsequentes. |
| `rates_csv_path` | Caminho do CSV usado no import de tarifas (`docs/postman/sample_rates.csv`). |
| `wa_phone_id`, `wa_business_id`, `wa_access_token`, `wa_verify_token`, `wa_webhook_secret` | Dados seed para testar integrações WhatsApp (incluindo secret usado no HMAC do webhook). |

### Assinatura do webhook

- `WA - Webhook Receive` calcula automaticamente o header `X-Hub-Signature-256` em um script *pre-request* usando HMAC SHA-256 do corpo bruto com a variável `wa_webhook_secret` (`sha256=<hex>`).
- Certifique-se de executar **WA - Create Connection** antes das requisições de webhook para que a API armazene o mesmo secret e verifique a assinatura corretamente.
- O payload de exemplo inclui `metadata.phone_number_id` e deve combinar com `wa_phone_id` para que o evento seja aceito.

## Fluxo recomendado

1. **Auth - Register** → **Auth - Login** (token e email são persistidos).
2. **Organization - Current** para preencher `org_id`.
3. Rodar sequência em **Providers** (Create → Save Credentials → Health Check).
4. Executar pasta **Rules** inteira (toggle final reativa a regra).
5. **Messages** (Send → Jobs → Job Detail).
6. **Rates**, **Reports** e **Integrations**.
7. Concluir com **Admin** e **Cleanup**.

Todos os requests foram configurados para funcionar em sequência via Newman, usando dados `seed` fornecidos por `make dev`.

## Executando testes automatizados

```bash
make postman-test
```

O comando utiliza `npx newman` com a coleção e ambiente acima. Certifique-se de que a API esteja rodando (`make dev`) antes de executar.

## Veja também

- [Referência da API](../api/API_REFERENCE.md)
- [Guia de operações](../operations/OPERATIONS.md)
- [Backlog priorizado](../backlog/README.md)
