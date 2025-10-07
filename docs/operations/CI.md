[Docs](../overview/README.md) › [Operações](./OPERATIONS.md)
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

Os valores `DATABASE_URL`, `REDIS_URL` e `VITE_API_BASE` já são definidos pelo próprio workflow ao usar `docker-compose`, mas podem
ser sobrescritos com secrets caso o pipeline aponte para infraestrutura gerenciada.

## Execução local dos jobs

Os alvos adicionados no [Makefile](../../Makefile) permitem reproduzir cada etapa:

- Certifique-se de ter Docker Compose disponível no host (`docker-compose` ou `docker compose`, respeitando a variável `DC` do Makefile).
- `make ci` roda todo o fluxo (`ci-backend`, `ci-frontend`, `ci-e2e`).
- `make ci-backend` recompila imagens Python e executa `alembic upgrade head` para detectar migrations quebradas.
- `make ci-frontend` instala dependências com `npm ci`, roda lint (`npm run lint`) e build (`npm run build`).
- `make ci-e2e` sobe a stack dockerizada, aguarda readiness (`/admin/health`) e executa a suíte Newman com export JUnit
  (`newman-report.xml`).

## Troubleshooting

- **Falhas no `ci-backend`**: normalmente apontam migrations inválidas ou requirements quebrados. Rode `make ci-backend` localmente e
  verifique os logs do comando `alembic upgrade head`.
- **Falhas no `ci-frontend`**: cheque alterações em lint rules (`eslint.config.js`) ou se o build Vite quebrou. Execute `npm run lint`
  e `npm run build` fora do Docker para iterar mais rápido.
- **Falhas no `ci-e2e`**: baixe o artefato `newman-report.xml` para identificar o request que falhou. Reproduza executando `make ci-e2e`
  ou seguindo o [guia do Postman/Newman](../postman/README.md). Caso a API não suba, confira variáveis sensíveis (`APP_SECRET_KEY`,
  `JWT_SECRET`) e o seed (`backend/scripts/seed.py`).

Reexecute apenas o job afetado pelo GitHub (`Re-run failed jobs`) sempre que possível para acelerar ciclos de feedback.
