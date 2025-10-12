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
