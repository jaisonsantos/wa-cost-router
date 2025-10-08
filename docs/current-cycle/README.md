[Docs](./README.md) › Ciclo Atual
# WA Cost Router — Ciclo Atual

A plataforma WA Cost Router orquestra provedores WhatsApp para reduzir custos de envio de mensagens com regras dinâmicas, métricas em tempo real e integrações prontas para múltiplos tenants. Este índice centraliza toda a documentação funcional e técnica.

## Quick start

```bash
cp backend/.env.example backend/.env  # ajuste segredos localmente
make dev                               # inicia db/redis, roda migrations + seed e sobe api/web/worker
```

O `.env` exemplo habilita o modo sandbox (`SANDBOX_PROVIDERS=true`), evitando chamadas HTTP externas e garantindo que seeds e testes retornem dados determinísticos.

Serviços expostos após `make dev`:

| Serviço  | Porta | Observações |
|----------|-------|-------------|
| API FastAPI | `http://localhost:8000` | Swagger em `/docs`, requer auth. |
| Frontend | `http://localhost:8080` | SPA Vite servida por Nginx. |
| Postgres | `localhost:5432` | Usuário `postgres` / senha `postgres`. |
| Redis | `localhost:6379` | Usado para jobs do worker. |

Outros comandos úteis:

| Comando | Descrição |
|---------|-----------|
| `make migrate` | Executa `alembic upgrade head` manualmente. |
| `make seed` | Reinsere dados demo sem recriar tabelas. |
| `make postman-test` | Executa a coleção Postman completa via Newman. |
| `make ci` | Reproduz localmente o pipeline (ver [Operações › Pipeline CI](../operations/OPERATIONS.md#pipeline-ci)). |
| `make down` | Remove serviços e volumes para limpeza rápida. |

## Navegação da documentação

| Área | Conteúdo |
|------|----------|
| [AGENTE do ciclo](./AGENTE.md) | Síntese executiva, pendências críticas e direcionadores de foco. |
| [Plano de Próxima Etapa](./NEXT_IMPLEMENTATION_PLAN.md) | Sequenciamento das entregas "Next Up" e dependências entre squads. |
| [Matriz de Casos de Uso](./USE_CASE_TRACEABILITY.md) | Status UC-01 a UC-04 com rastreabilidade para backlog, roadmap e documentação de suporte. |
| [Índice do Backlog por Caso de Uso](../backlog/INDEX_BY_USE_CASE.md) | Visão cruzada dos itens priorizados por UC e links para cada história. |
| [Backlog Prioritário](../backlog/README.md) | Itens P1/P2/P3 com subtarefas e referências cruzadas. |
| [Arquitetura](../architecture/ARCHITECTURE.md) | Componentes principais, fluxos e responsabilidades. |
| [Modelagem de Dados](../architecture/DATA_MODEL.md) | Tabelas, relacionamentos e entidades de domínio. |
| [Referência da API](../api/API_REFERENCE.md) | Contratos dos endpoints e links para a coleção Postman. |
| [Operações](../operations/OPERATIONS.md) | Rotinas de deploy, observabilidade, pipeline CI e troubleshooting. |
| [CI Pipeline (detalhes)](../operations/CI.md) | Segredos, execução manual e troubleshooting aprofundado. |
| [Migrations](../operations/MIGRATIONS.md) | Pipeline de migrações Alembic e ordem de execução. |
| [Deployment](../operations/DEPLOYMENT.md) | Estratégia recomendada para ambientes gerenciados. |
| [Segurança](../security/SECURITY.md) | Controles atuais, riscos conhecidos e próximos passos. |
| [Preços](../pricing/PRICING_BILLING.md) | Modelo de cobrança e cálculos de economia. |
| [Roadmap](../roadmap/ROADMAP.md) | Evolução planejada por trimestre. |
| [Postman](../postman/README.md) | Guia de uso da coleção e variáveis de ambiente. |

## Convenções chave

- **Autenticação**: JWT assinado com `JWT_SECRET`; tokens de provedores criptografados com Fernet (`APP_SECRET_KEY`).
- **Multi-tenant**: todo acesso a dados é filtrado por `org_id`. O webhook WhatsApp ainda precisa mapear `phone_id → org_id` (vide backlog P1).
- **Logs & métricas**: `/admin/metrics` expõe métricas Prometheus; proteger em ambiente produtivo.
- **Seeds**: `backend/scripts/seed.py` popula apenas dados demo (org, usuário, rates, eventos) sem criar tabelas.

## Estrutura de diretórios

```
backend/         # API FastAPI, migrations Alembic, scripts
src/             # Frontend Vite/React
docs/            # Documentação centralizada (este índice)
Makefile         # Fluxos de desenvolvimento e QA
```

## Como contribuir

1. Crie uma branch a partir de `main` usando Conventional Commits.
2. Rode `make dev` para preparar o ambiente e validar o build.
3. Execute `make postman-test` antes de abrir PRs que afetem a API.
4. Atualize os documentos relevantes dentro da árvore `docs/` quando alterar contratos.

## Veja também

- [Referência completa da API](../api/API_REFERENCE.md)
- [Guia de operações](../operations/OPERATIONS.md)
- [Coleção Postman](../postman/README.md)
