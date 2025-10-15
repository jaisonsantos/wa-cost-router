# WA Cost Router

Roteamento inteligente de mensagens WhatsApp com foco em redução de custos, multi-tenant seguro e relatórios em tempo real.

## Quick Start

```bash
cp backend/.env.example backend/.env  # configure secrets locais
make dev                               # inicia db/redis, migrations, seed e sobe api/web/worker
```

O `.env` exemplo já habilita o modo sandbox (`SANDBOX_PROVIDERS=true`), que simula chamadas aos provedores WhatsApp e mantém as
respostas determinísticas para `make dev`, `make ci` e a coleção Postman.

### Sandboxes SMS / E-mail

- **Twilio (SMS)** – use `AC000…` como `account_sid`, um `auth_token` alfanumérico e o número sandbox `+15558675309`. O campo `inbound_verify_token` deve corresponder ao token usado pelos webhooks (seed padrão: `demo-sms-auth-token`). Após salvar, execute o botão "Testar" na página *Providers* para validar a conexão.
- **SendGrid (E-mail)** – preencha uma `api_key` iniciada em `SG.`, o remetente padrão (`noreply@demo.local` no seed), o `webhook_token` e o `inbound_signing_secret`. O health check disponível na UI confirma se o segredo está sincronizado com o simulador de Event Webhook.
- Todos os schemas de formulário estão expostos em `GET /providers` via `provider_form_schema`, permitindo automação (ex.: Postman/Newman) sem hardcode de campos.

Comandos úteis:

- `make migrate` – aplica migrations Alembic.
- `make seed` – repovoa dados demo (sem criar tabelas).
- `make postman-test` – executa a coleção Postman via Newman.
- `make down` – derruba todos os serviços e volumes.
- `make lint-backend` – valida estilo/código do backend com Ruff.
- `make test-backend` – executa a suíte Pytest localizada em `backend/tests`.
- `npm run test:e2e` – executa a suíte Playwright contra a stack sandbox (requer serviços do `make dev` ativos).

### Billing (Stripe)

- Checkout e portal já enviam `automatic_tax={"enabled": true}`; os webhooks populam `billing_invoice` com impostos agregados por invoice e atualizam `billing_subscription.tax_amount_total_minor`.
- A métrica `billing_tax_applied_total{org_id}` expõe o acumulado de impostos (em minor units) consumido pela organização.
- Habilite `BILLING_USAGE_SYNC_ENABLED=true` e garanta `STRIPE_SECRET_KEY` configurado no `.env` para que o worker publique `UsageRecord` agregando as mensagens faturáveis por dia.
- O worker `billing_usage` roda na fila dedicada (já adicionada ao `backend/worker.py`) e respeita `BILLING_USAGE_BATCH_SIZE` por execução.
- Retries aplicam `exponential backoff` configurável via `BILLING_USAGE_RETRY_BASE_SECONDS`/`BILLING_USAGE_RETRY_MAX_SECONDS`; falhas e sucessos são expostos na métrica Prometheus `billing_usage_records_total{org_id,status}`.
- O worker `billing_reconcile` (fila `billing_reconcile`) compara invoices locais × Stripe diariamente e registra `billing_reconcile_drift{org_id}`; configure alertas para valores >1.
- Para disparo manual de usage, utilize `POST /billing/usage/sync` (retorna o `job_id` enfileirado) — útil para reprocessar janelas específicas em homologação.

### Recriando seeds após novas migrations

Sempre que o modelo de dados for alterado por uma migration, aplique o schema atualizado e regenere os dados sandbox para manter a base consistente:

```bash
make migrate
make seed
```

Se preferir executar manualmente, use `docker compose run --rm api alembic upgrade head` seguido de `docker compose run --rm api python scripts/seed.py`.

### Testes End-to-End

A suíte Playwright, disponível em `tests/e2e`, simula envios via API sandbox (`SANDBOX_PROVIDERS=true`) e valida na UI os fluxos de e-mail e SMS.

1. Suba a stack local completa: `make dev`.
2. Na primeira execução, instale navegadores Playwright: `npx playwright install --with-deps`.
3. Execute os testes: `npm run test:e2e`.

Os testes utilizam o usuário demo (`admin@demo.local` / `demo123`) criado pelo seed automático e limpam-se sozinhos ao final.

## Contribuindo

Antes de abrir um Pull Request, instale as dependências de desenvolvimento do backend e garanta que lint/testes passam localmente:

```bash
pip install -r backend/requirements-dev.txt
make lint-backend
make test-backend
```

## CI/CD

O workflow [CI](.github/workflows/ci.yml) roda em pushes e pull requests para `main`, garantindo qualidade antes do merge.
Ele é dividido em três jobs principais:

- **backend** – constrói a imagem da API, aplica migrations em um banco efêmero e valida dependências do worker.
- **frontend** – instala dependências Node, roda `npm run lint` e gera o build Vite para checar que a UI compila.
- **e2e** – sobe a stack via Docker Compose e executa os testes Postman/Newman contra o backend publicado.

Use `make ci` para replicar localmente a sequência de checks descrita em [Operações › Pipeline CI](docs/operations/OPERATIONS.md#pipeline-ci).

### Auto-fix do Codex após falhas

Quando o workflow `CI` termina com status `failure`, o arquivo
[`codex-autofix.yml`](.github/workflows/codex-autofix.yml) é disparado. Ele só
executa se o segredo `OPENAI_API_KEY` estiver configurado no repositório e se a
falha tiver ocorrido **após** o merge dessa automação na `main`.

- Branches que já tinham falhas antes do merge precisam ser reexecutadas (por
  exemplo, via _Re-run jobs_ ou push de novos commits) para que o evento
  `workflow_run` dispare novamente já com o auto-fix disponível.
- Branches criadas a partir da `main` atual já carregam o workflow e, se
  apresentarem falhas na `CI`, terão o auto-fix executado automaticamente na
  mesma tentativa que resultar em `failure`.

O auto-fix baixa a branch que falhou, roda o Codex com o prompt guardrail, tenta
aplicar um patch mínimo, reexecuta os testes e, em caso de sucesso, abre um PR
temporário com as correções para revisão humana.

## Documentação

- [Ciclo atual (roadmap, plano e governança)](docs/current-cycle/README.md)
- [Histórico de ciclos anteriores](docs/history/2024-cycle-mvp/README.md)
- [Matriz de casos de uso e rastreabilidade](docs/current-cycle/USE_CASE_TRACEABILITY.md)
- [Backlog priorizado](docs/backlog/README.md)
- [Referência da API](docs/api/API_REFERENCE.md)
- [Coleção Postman + ambiente](docs/postman/README.md)

## Stack

- Backend: FastAPI + SQLAlchemy + Alembic.
- Banco: PostgreSQL 16, cache/filas em Redis 7.
- Worker: RQ para processamento assíncrono.
- Frontend: Vite/React (ver pasta `src/`).

Licença MIT.
