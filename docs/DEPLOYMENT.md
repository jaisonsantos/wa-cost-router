# Deployment Guide

## Infraestrutura

- **Aplicação**: FastAPI (8000), worker RQ (opcional), frontend (Nginx).
- **Banco**: Postgres gerenciado (TLS, backups).
- **Cache/Fila**: Redis (AWS ElastiCache / Azure Cache).
- **Proxy**: Nginx/Caddy com TLS (Let’s Encrypt).

## Passo a Passo

1. **Preparar `.env`** com `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `APP_SECRET_KEY`, `STRIPE_SECRET_KEY`, `WA_VERIFY_TOKEN`, `SMTP_*`, etc.
2. **Build & Deploy**
   ```bash
   docker-compose pull
   docker-compose run --rm api alembic upgrade head
   docker-compose up -d api worker web
   ```
3. **Reverse Proxy**
   - TLS + HSTS.
   - Rate limit (100 req/min/org).
   - Headers de segurança (CSP, X-Frame-Options).
4. **CORS/HTTPS**
   - Configurar origens via env (ex: `FRONTEND_URL=https://app.example.com`).
   - Forçar HTTPS via proxy.
5. **Monitoramento**
   - Prometheus + Grafana (coletar `/admin/metrics`).
   - Alertas: erro 5xx >2%, latência >3s, economia negativa.
6. **Observabilidade**
   - Logging estruturado.
   - Traço mínimo de requisições (request_id).
7. **Pós-deploy**
   - Rodar testes de fumaça (curl simulate → send → job).
   - Verificar dashboards e métricas.
   - Garantir backup inicial.

## Dimensionamento Inicial

- API: 1 réplica (2 vCPU, 4GB RAM).
- Worker: 1 réplica (opcional).
- Postgres: db.t3.medium (ou equivalente).
- Redis: cache.t3.micro.

## Planos de rollback

- `docker-compose rollback` (usar tags imutáveis).
- Restaurar backup do banco em caso de migração problemática.
