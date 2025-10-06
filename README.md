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
