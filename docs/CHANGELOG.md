# Changelog

# v0.1.3 (2025-10-07)
- Corrigido erro `ModuleNotFoundError: app` ao rodar migrations dentro do container, garantindo que Alembic enxergue os módulos do backend.
- Removido atributo `version` obsoleto do `docker-compose.yml` para evitar avisos nas versões recentes do Docker Compose.

# v0.1.2 (2025-10-07)
- Adicionado `Makefile` com atalhos para subir stack, logs, migrations e seeds.
- Atualizados README, BACKEND_README e docs de operações com referência aos novos comandos.
- Registrada a manutenção operacional no log de iterações.

## v0.1.1 (2025-10-06)
- Adicionado builder visual de regras com suporte a países, categorias, templates e fallback.
- Atualizada página de regras para refletir contratos reais da API e exibir provedores configurados.
- Documentação revisada para marcar a entrega do formulário de regras.

## v0.1.0 (2025-10-06)
- Auditoria inicial do código WA Cost Router.
- Identificados gaps de multi-tenancy, segurança e migrations.
- Criados planos de ação, documentação e roadmap.
