[Docs](../current-cycle/README.md) › [Operações](./OPERATIONS.md)
# CI avançado

Este apêndice complementa a seção [Pipeline CI](./OPERATIONS.md#pipeline-ci) com detalhes sobre configuração de segredos, execução
manual e dicas de troubleshooting.

## Segredos e variáveis do workflow

A stack Docker usa os mesmos valores do arquivo [`.env.example`](../../.env.example), portanto é recomendável mapear os seguintes
segredos no GitHub:

| Nome do secret | Uso no pipeline | Observações |
|----------------|-----------------|-------------|
| `APP_SECRET_KEY` | Encriptação de dados sensíveis no backend. | Necessário para iniciar a API e executar seeds. |
| `JWT_SECRET` | Assinatura de tokens emitidos nos testes. | Mantém compatibilidade com `JWT_ALG=HS256`. |
| `WA_VERIFY_TOKEN` | Valida o webhook simulado durante os testes Newman. | Deve coincidir com `WA_VERIFY_TOKEN` usado em `docs/postman/`. |
| `WA_APP_SECRET` | Assinatura dos callbacks WhatsApp. | Reutiliza o valor fake de desenvolvimento quando não há webhook real. |
| `STRIPE_SECRET_KEY` e `STRIPE_WEBHOOK_SECRET` | Placeholders para integrações futuras. | Pode usar os valores fake do `.env.example` até que billing esteja ativo. |
| `SMTP_HOST` e `SMTP_PORT` | Permitem enviar emails nos cenários de teste. | Mantêm apontamento para `mailhog`. |
| `SENDGRID_API_KEY` / `SENDGRID_DEFAULT_SENDER_EMAIL` | Exercitam o conector sandbox de e-mail. | Use chaves fakes; o workflow publica valores `sandbox-*` por padrão. |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` / `TWILIO_MESSAGING_SERVICE_SID` | Necessários para validar envios/recebimentos SMS nos testes sandbox. | Use os valores de `.env.example` ou equivalentes mascarados. |
| `SANDBOX_PROVIDERS`, `SANDBOX_LATENCY_MS`, `SANDBOX_FAILURE_RATE` | Garante que todos os conectores rodem em modo fake determinístico. | Workflow força `true/0/0`; ajuste manualmente para simular latência/falhas. |
| `RATE_LIMIT_MESSAGES_PER_MIN` / `RATE_LIMIT_LOGIN_PER_MIN` | Controlam os limites de requisições por minuto utilizados nos testes automatizados. | Defaults exportados pelo workflow (`120` e `20`), ajustáveis conforme necessidade. |

Os valores `DATABASE_URL`, `REDIS_URL` e `VITE_API_BASE` já são definidos pelo próprio workflow ao usar `docker-compose`, mas podem
ser sobrescritos com secrets caso o pipeline aponte para infraestrutura gerenciada.

## Execução local dos jobs

Os alvos adicionados no [Makefile](../../Makefile) permitem reproduzir cada etapa:

- Certifique-se de ter Docker Compose disponível no host (`docker-compose` ou `docker compose`, respeitando a variável `DC` do Makefile).
- `make ci` roda todo o fluxo (`ci-backend`, `test-backend-multichannel`, `ci-frontend`, `test-frontend`, `ci-e2e`).
- `make ci-backend` recompila imagens Python e executa `alembic upgrade head` para detectar migrations quebradas.
- `make test-backend-multichannel` executa apenas os testes Pytest relacionados a email/SMS e sandbox multi-channel usando credenciais fakes exportadas pelo script.
- `make ci-frontend` instala dependências com `npm ci`, roda lint (`npm run lint`) e build (`npm run build`).
- `make test-frontend` roda a suíte Vitest em modo não interativo (`CI=true`).
- `make ci-e2e` sobe a stack dockerizada, aguarda readiness (`/admin/health`), executa as suítes Newman (incluindo a pasta **Multi-Channel Regression**) e, antes do teardown, reutiliza `scripts/test-e2e.sh` para disparar o Playwright com `SANDBOX_PROVIDERS=true`.
- `make test-e2e` apenas executa o Playwright contra uma stack já inicializada (`make dev` ou `make ci-e2e`) validando o fluxo UI/API de mensagens multi-canal.

## Troubleshooting

- **Bloqueio administrativo (billing)**: se o workflow não iniciar e exibir a mensagem sobre pagamentos recentes/spending limit, execute `make ci-lite` como mitigação temporária e siga o [plano de correção da pipeline](./CI_RECOVERY_PLAN.md) para coordenar desbloqueio financeiro e comunicação. Publique o resultado manual com `make ci-lite-publish repo=<owner/repo> pr=<n>` (ou `scripts/ci_lite_publish.py`) para registrar o status no PR enquanto o Actions estiver indisponível.

- **Falhas no `ci-backend`**: normalmente apontam migrations inválidas ou requirements quebrados. Rode `make ci-backend` localmente e
  verifique os logs do comando `alembic upgrade head`.
- **Falhas no `ci-frontend`**: cheque alterações em lint rules (`eslint.config.js`) ou se o build Vite quebrou. Execute `npm run lint`
  e `npm run build` fora do Docker para iterar mais rápido.
- **Falhas no `ci-e2e`**: baixe o artefato `newman-report.xml` para identificar o request que falhou. Reproduza executando `make ci-e2e`
  ou seguindo o [guia do Postman/Newman](../postman/README.md). Falhas na pasta **Contacts** normalmente indicam problemas nos endpoints `/contacts`
  ou em permissões de upload (`POST /contacts/imports`); valide migrations `007-009` e o worker RQ. Caso a API não suba, confira variáveis sensíveis
  (`APP_SECRET_KEY`, `JWT_SECRET`) e o seed (`backend/scripts/seed.py`).
- **Playwright reporta que a API está indisponível**: confirme se o `scripts/test-e2e.sh` está apontando para a mesma URL usada pelo docker compose (`E2E_API_BASE_URL=http://localhost:8000`). Quando executado isoladamente, suba a stack com `make dev` ou exporte `SKIP_PLAYWRIGHT_INSTALL=1` para evitar reinstalação de browsers toda vez.
- **Erros em sandbox de e-mail/SMS**: verifique se os envs `SENDGRID_API_KEY`, `SENDGRID_DEFAULT_SENDER_EMAIL`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` e `TWILIO_FROM_NUMBER` estão preenchidos. Os scripts de teste já exportam defaults, mas um override vazio via shell pode gerar `ValueError` nas factories.

Reexecute apenas o job afetado pelo GitHub (`Re-run failed jobs`) sempre que possível para acelerar ciclos de feedback.
