# WA Cost Router

> Roteamento inteligente de mensagens WhatsApp com economia de custos e métricas em tempo real.

[![Docker](https://img.shields.io/badge/Docker-ready-blue)](#quick-start) [![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Quick Start

1. Clone o repositório e configure as variáveis locais:

   ```bash
   git clone <repo>
   cd wa-cost-router
   cp backend/.env.example backend/.env  # preencha secrets
   ```

2. Suba o ambiente com o Makefile (atalhos para o `docker-compose`):

   ```bash
   make dev        # build + sobe tudo em foreground
   # ou
   make up         # sobe em background
   ```

3. Aplique migrations/seeds quando necessário:

   ```bash
   make migrate
   make seed-providers
   ```

- API: http://localhost:8000
- Frontend: http://localhost:8080

Para mais comandos (logs, shells, limpeza) consulte a [referência do Makefile](#makefile) e `docs/OPERATIONS.md`.

## Endpoints Essenciais

| Método | Rota | Descrição |
| --- | --- | --- |
| POST | `/messages/send` | Envio com idempotência e fallback |
| GET | `/messages/jobs` | Histórico de jobs da organização |
| GET | `/reports/dashboard-metrics` | Métricas de custo e sucesso |
| POST | `/rules/simulate-advanced` | Simulador de economia |
| POST | `/providers/credentials` | Configuração de provedores |

Mais detalhes em [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md).

## Demo rápida

```bash
# Simulação
curl -X POST http://localhost:8000/rules/simulate-advanced \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"countries":["BR"],"volumes":{"BR":1000},"category":"marketing"}'

# Envio idempotente
curl -X POST http://localhost:8000/messages/send \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"idempotency_key":"demo-1","to_number":"+5511999999999","template_id":"welcome","template_category":"marketing","variables":{}}'

# Consulta de job
curl http://localhost:8000/messages/jobs/$JOB_ID \
  -H "Authorization: Bearer $TOKEN"
```

## Documentação

- [Arquitetura](docs/ARCHITECTURE.md)
- [Modelagem de Dados](docs/DATA_MODEL.md)
- [Operações](docs/OPERATIONS.md)
- [Segurança](docs/SECURITY.md)
- [Roadmap](docs/ROADMAP.md)

## Makefile

O repositório agora inclui um `Makefile` com os comandos mais comuns:

| Comando | Descrição |
| --- | --- |
| `make dev` | Builda e sobe todos os serviços em foreground |
| `make up` | Sobe os serviços em modo detach |
| `make down` | Derruba os serviços |
| `make logs` / `make logs-api` / `make logs-web` | Acompanha logs |
| `make migrate` | Executa as migrations Alembic |
| `make seed` / `make seed-providers` | Popula dados demo e provedores |
| `make clean` | Remove containers e volumes |
| `make shell-api` / `make shell-db` | Abre shell no container API ou psql |

Rode `make help` para listar todos os alvos disponíveis.

## Licença

MIT.
