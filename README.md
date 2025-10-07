# WA Cost Router

Roteamento inteligente de mensagens WhatsApp com foco em redução de custos, multi-tenant seguro e relatórios em tempo real.

## Quick Start

```bash
cp backend/.env.example backend/.env  # configure secrets locais
make dev                               # inicia db/redis, migrations, seed e sobe api/web/worker
```

Comandos úteis:

- `make migrate` – aplica migrations Alembic.
- `make seed` – repovoa dados demo (sem criar tabelas).
- `make postman-test` – executa a coleção Postman via Newman.
- `make down` – derruba todos os serviços e volumes.

## CI/CD

O workflow [CI](.github/workflows/ci.yml) roda em pushes e pull requests para `main`, garantindo qualidade antes do merge.
Ele é dividido em três jobs principais:

- **backend** – constrói a imagem da API, aplica migrations em um banco efêmero e valida dependências do worker.
- **frontend** – instala dependências Node, roda `npm run lint` e gera o build Vite para checar que a UI compila.
- **e2e** – sobe a stack via Docker Compose e executa os testes Postman/Newman contra o backend publicado.

Use `make ci` para replicar localmente a sequência de checks descrita em [Operações › Pipeline CI](docs/operations/OPERATIONS.md#pipeline-ci).

## Documentação

- [Visão geral e índice completo](docs/overview/README.md)
- [Referência da API](docs/api/API_REFERENCE.md)
- [Coleção Postman + ambiente](docs/postman/README.md)
- [Backlog priorizado](docs/backlog/README.md)

## Stack

- Backend: FastAPI + SQLAlchemy + Alembic.
- Banco: PostgreSQL 16, cache/filas em Redis 7.
- Worker: RQ para processamento assíncrono.
- Frontend: Vite/React (ver pasta `src/`).

Licença MIT.
