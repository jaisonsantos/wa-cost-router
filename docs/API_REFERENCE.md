# API Reference (Resumo)

Todas as rotas abaixo exigem `Authorization: Bearer <token>` salvo indicação contrária.

## Autenticação
- `POST /auth/register` `{ email, password, org_name }` → `{ access_token }`
- `POST /auth/login` `{ email, password }` → `{ access_token }`

## Mensagens
- `POST /messages/send` → `SendMessageResponse`
- `GET /messages/jobs?status=...` → `MessageJob[]`
- `GET /messages/jobs/{job_id}` → detalhes + tentativas

## Regras
- `GET /rules`
- `POST /rules`
- `PATCH /rules/{id}` (payload completo)
- `POST /rules/{id}/toggle`
- `POST /rules/simulate-advanced`

## Relatórios
- `GET /reports/dashboard-metrics?days=7`
- `GET /reports/provider-metrics?days=7`
- `GET /reports/summary?from=YYYY-MM-DD&to=YYYY-MM-DD`

## Provedores
- `GET /providers`
- `POST /providers`
- `POST /providers/credentials`
- `POST /providers/{id}/health`
- `DELETE /providers/{id}/credentials`

## Tarifas
- `GET /rates`
- `POST /rates/import_csv`

## Integrações
- `POST /integrations/wa/connections`
- `GET /integrations/wa/webhook`
- `POST /integrations/wa/webhook`

## Admin
- `GET /admin/health`
- `GET /admin/metrics`
