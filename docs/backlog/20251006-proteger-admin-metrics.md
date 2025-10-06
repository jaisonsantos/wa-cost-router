---
title: "Proteger endpoint /admin/metrics"
type: hardening
prio: P1
estimate: "1d"
owner: "unassigned"
depends_on: []
---

## Contexto

O endpoint [`GET /admin/metrics`](../api/API_REFERENCE.md) está exposto sem autenticação, permitindo que qualquer usuário acesse métricas internas Prometheus. Em ambientes públicos isso pode revelar volumes, erros e configurações sensíveis.

## Escopo

- Implementar proteção via API key, Basic Auth ou restrição por IP/Trusted proxy.
- Permitir configuração do mecanismo via env (ex.: `METRICS_AUTH_TOKEN`).
- Atualizar `docker-compose.yml`/infra para fornecer credenciais padrão apenas em desenvolvimento.
- Documentar uso no guia de operações.

## Acceptance Criteria

- Requisições sem credencial retornam 401/403.
- Coleção Postman inclui header/opção para autenticar no endpoint.
- Guia de [Operações](../operations/OPERATIONS.md) descreve como habilitar/desabilitar o acesso em produção.
- Monitoramento automatizado (New Relic/Grafana Agent) consegue autenticar usando secret configurado.

## Subtasks

- [ ] Adicionar middleware simples (ex.: chave compartilhada) ou integrar com dependência FastAPI custom.
- [ ] Criar variáveis em `.env.example` para o novo secret.
- [ ] Atualizar Postman request **Admin - Metrics** para enviar o header correto.
- [ ] Documentar passos em `docs/security/SECURITY.md` e `docs/operations/OPERATIONS.md`.

## Referências

- [Segurança](../security/SECURITY.md)
- [Operações](../operations/OPERATIONS.md)
- Código: [`backend/app/api/admin.py`](../../backend/app/api/admin.py)

## Out of Scope

- Implementar RBAC completo para outras rotas administrativas.
- Configuração de mTLS para scraping (avaliar futuramente).
