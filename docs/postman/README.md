[Docs](../current-cycle/README.md) › [Postman](./README.md)
# Coleção Postman

A coleção `WA Cost Router` cobre 100% dos endpoints do backend com variáveis encadeadas para um fluxo E2E completo.

> ℹ️ A stack local (`make dev`/`make ci`) roda com `SANDBOX_PROVIDERS=true`, portanto os requests de Providers/Messages executam em memória sem atingir provedores externos. Ajuste `SANDBOX_LATENCY_MS` e `SANDBOX_FAILURE_RATE` para simular cenários diferentes quando necessário.

## Estrutura

1. **Auth** – registra usuário aleatório (`postman+timestamp`) com senha forte gerada no runtime e efetua login (token salvo automaticamente).
2. **Organization** – obtém `org_id` via `/orgs/current`.
3. **Providers** – cria provedor WhatsApp (360dialog), salva credenciais fake e executa health check.
4. **Rules** – lista, cria, atualiza e alterna regras, incluindo simulação avançada.
5. **Messages** – envia mensagem, lista jobs, consulta detalhes do job usando `job_id` capturado e inclui a requisição opcional **Messages - Rate Limit Demo** para validar respostas `429`.
6. **Contacts** – dispara importação assíncrona (`POST /contacts/imports`), lista catálogos, cria contato, edita atributos, alterna status ativo/inativo e consulta histórico de consentimento.
7. **Contact Segments** – cria segmento, atualiza metadados, associa/desassocia o contato criado e configura política de limites/opt-out.
8. **Rates** – consulta tarifas e importa CSV de exemplo (`docs/postman/sample_rates.csv`) usando o `provider_name` do provedor criado na etapa Providers.
9. **Reports** – consome métricas de dashboard, resumo e métricas por provedor.
10. **Integrations** – cria conexão WA, valida webhook (`hub.verify_token`) e envia payload de webhook (repetir a criação com o mesmo `phone_id` apenas atualiza o registro).
11. **Admin** – checa `/admin/health` e `/admin/metrics`.
12. **Cleanup** – remove credenciais do provedor criado durante o fluxo.

Scripts de coleção adicionam o header `Authorization` automaticamente sempre que `token` estiver definido e validam que todas as respostas retornem status 2xx.

## Variáveis de ambiente

Arquivo: [`wa-cost-router.postman_environment.json`](./wa-cost-router.postman_environment.json)

| Variável | Descrição |
|----------|-----------|
| `base_url` | URL base da API (default `http://localhost:8000`). |
| `email` / `password` | Credenciais seed (`admin@demo.local` / `demo123`) usadas como fallback até o prerequest gerar valores fortes por execução. |
| `token` | JWT salvo pelos testes (não preencha manualmente). |
| `org_id`, `provider_id`, `rule_id`, `job_id`, `contact_id`, `segment_id`, `contact_import_job_id` | IDs capturados automaticamente para uso em chamadas subsequentes. |
| `rates_csv_path` | Caminho do CSV usado no import de tarifas (`docs/postman/sample_rates.csv`). |
| `contacts_csv_path` | Caminho do CSV usado no import de contatos (`docs/postman/sample_contacts.csv`). |
| `rate_limit_demo_enabled` | Quando `true`, o request **Messages - Rate Limit Demo** dispara chamadas adicionais para demonstrar `429` (requer ajustar os limites da API para valores baixos). |
| `wa_phone_id`, `wa_business_id`, `wa_access_token`, `wa_verify_token`, `wa_webhook_secret` | Dados seed para testar integrações WhatsApp (incluindo secret usado no HMAC do webhook). |

### Assinatura do webhook

- `WA - Webhook Receive` calcula automaticamente o header `X-Hub-Signature-256` em um script *pre-request* usando HMAC SHA-256 do corpo bruto com a variável `wa_webhook_secret` (`sha256=<hex>`).
- Certifique-se de executar **WA - Create Connection** antes das requisições de webhook para que a API armazene o mesmo secret; quando o header de assinatura não for enviado, os eventos serão ignorados com `status: ignored`.
- O payload de exemplo inclui `metadata.phone_number_id` e deve combinar com `wa_phone_id` para que o evento seja aceito.

## Fluxo recomendado

1. **Auth - Register** → **Auth - Login** (token e email são persistidos).
2. **Organization - Current** para preencher `org_id`.
3. Rodar sequência em **Providers** (Create → Save Credentials → Health Check).
4. Executar pasta **Rules** inteira (toggle final reativa a regra).
5. **Messages** (Send → Jobs → Job Detail).
6. **Contacts** (Import CSV → List → Create → Update → Opt-Out → Opt-In → Consent History) utilizando os IDs armazenados automaticamente.
7. **Contact Segments** (Create → List → Update → Add Contacts → Remove Contact → Upsert Policy → Delete) para validar o fluxo de segmentação.
8. **Rates**, **Reports** e **Integrations**.
9. Concluir com **Admin** e **Cleanup**.

Todos os requests foram configurados para funcionar em sequência via Newman, usando dados `seed` fornecidos por `make dev`.

### Demonstração de rate limit (`429 Too Many Requests`)

1. Ajuste os limites do backend exportando, no terminal, valores pequenos (ex.: `RATE_LIMIT_MESSAGES_PER_MIN=2 RATE_LIMIT_LOGIN_PER_MIN=2 make dev`).
2. No Postman, altere a variável de ambiente `rate_limit_demo_enabled` para `true`.
3. Execute **Messages - Rate Limit Demo**: a primeira chamada confirma o header `X-RateLimit-Remaining`; as chamadas subsequentes feitas via script retornam `429` com `Retry-After` e `X-RateLimit-Remaining: 0`.
4. Restaure os limites padrão removendo as variáveis ou definindo valores maiores antes de repetir o fluxo normal de mensagens.

## Executando testes automatizados

```bash
make postman-test
```

O comando utiliza `npx newman` com a coleção e ambiente acima. Certifique-se de que a API esteja rodando (`make dev`) antes de executar.

## Veja também

- [Referência da API](../api/API_REFERENCE.md)
- [Guia de operações](../operations/OPERATIONS.md)
- [Backlog priorizado](../backlog/README.md)
