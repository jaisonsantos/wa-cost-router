[Docs](../overview/README.md) › [Operações](./OPERATIONS.md) › Deployment
# Deployment Guide

## Infraestrutura recomendada

- **Aplicação**: container FastAPI (8000) atrás de proxy com TLS.
- **Worker**: processo RQ separado; escala horizontal conforme volume.
- **Frontend**: build estático servido por Nginx ou CDN.
- **Banco**: PostgreSQL gerenciado com backups automáticos e TLS obrigatório.
- **Cache/Fila**: Redis gerenciado (ElastiCache/MemoryDB/Redis Cloud).
- **Proxy**: Nginx/Caddy com HTTPS, HSTS e rate limiting.

## Pipeline sugerido

1. Provisionar infraestrutura (Postgres, Redis, storage de secrets).
2. Publicar imagens com tags imutáveis (`backend`, `worker`, `web`).
3. Aplicar migrations:
   ```bash
   docker-compose run --rm api alembic upgrade head
   ```
4. Rodar `docker-compose up -d api worker web` (ou equivalente no orquestrador).
5. Conectar domínio ao proxy e configurar TLS automático.

## Configuração obrigatória

- `DATABASE_URL`, `REDIS_URL`, `APP_SECRET_KEY`, `JWT_SECRET`, `WA_VERIFY_TOKEN` devem ser injetados via secrets manager.
- Configure `ALLOWED_ORIGINS`/`FRONTEND_URL` para limitar CORS.
- Habilite health-checks no orquestrador para `/admin/health` (somente interno).
- Proteja `/admin/metrics` por autenticação ou rede privada.

## Observabilidade & segurança

- Coletar métricas Prometheus de `/admin/metrics` em intervalos de 15s.
- Exportar logs estruturados (JSON) para stack centralizada (CloudWatch, ELK, Loki).
- Ativar alertas: taxa de erro HTTP 5xx > 2%, aumento de `failed_final` em `MessageJob`, consumo de Redis acima de 80%.
- Garantir rotação e armazenamento seguro de `APP_SECRET_KEY`/`JWT_SECRET`.

## Pós-deploy

1. Executar smoke tests: login → criar provider → credenciais → `POST /messages/send` → `GET /messages/jobs`.
2. Rodar `make postman-test` apontando para o ambiente hospedado (ajuste `base_url` no ambiente Postman).
3. Validar dashboards em `/reports/dashboard-metrics` e `/reports/provider-metrics`.

## Planos de rollback

- Manter dumps recentes do banco (`pg_dump`) antes de migrations críticas.
- Versionar as imagens para reverter com `docker compose up -d api=<tag_anterior>`.
- Reaplicar seeds apenas em ambientes de demonstração.

## Veja também

- [Operações & runbooks](./OPERATIONS.md)
- [Guia de migrations](./MIGRATIONS.md)
- [Segurança](../security/SECURITY.md)
