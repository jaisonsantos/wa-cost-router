# WA Cost Router - Backend Implementation

## 🚀 Quick Start

```bash
# Clone and install frontend deps (opcional para rodar lint/local dev)
git clone <repo>
cd wa-cost-router
npm install

# Subir stack via Makefile (atalhos para docker-compose)
make dev           # build + sobe em foreground
# ou
make up            # sobe em background

# Logs e shutdown
make logs-api
make down
```

Os comandos originais com `docker-compose` continuam válidos; consulte `make help` para a lista completa de atalhos.

The API will be available at `http://localhost:8000`  
The web frontend will be at `http://localhost:8080`

## 📋 Architecture

- **API**: FastAPI (Python 3.11) on port 8000
- **Database**: PostgreSQL 16 on port 5432
- **Cache/Queue**: Redis 7 on port 6379
- **Worker**: RQ worker for background jobs
- **Web**: Nginx serving React frontend on port 8080

## 🔑 Default Credentials

```
Email: admin@demo.local
Password: demo123
```

## 📡 API Endpoints

### Authentication
- `POST /auth/register` - Register new user + org
- `POST /auth/login` - Login and get JWT token

### Organizations
- `GET /orgs/current` - Get current org info (requires auth)

### WhatsApp Integration
- `POST /integrations/wa/connections` - Add WA connection
- `GET /integrations/wa/webhook` - Webhook verification
- `POST /integrations/wa/webhook` - Receive WA events

### Rates
- `GET /rates` - List rate cards
- `POST /rates/import_csv` - Import CSV with rates

### Events
- `GET /events` - List message events (supports filters)

### Reports
- `GET /reports/summary` - Get cost summary
- `GET /reports/dashboard-metrics` - Complete dashboard metrics (savings, success rate, top countries/templates)
- `GET /reports/provider-metrics` - Performance metrics by provider

### Rules
- `GET /rules` - List routing rules
- `POST /rules` - Create new rule
- `PATCH /rules/{id}` - Update rule
- `POST /rules/{id}/toggle` - Toggle rule active status
- `POST /rules/simulate` - Simulate cost savings (basic)
- `POST /rules/simulate-advanced` - Advanced simulation with breakdown by country and provider

### Providers
- `GET /providers` - List all providers
- `POST /providers` - Create new provider
- `POST /providers/credentials` - Set provider credentials
- `POST /providers/{id}/health` - Health check provider
- `DELETE /providers/{id}/credentials` - Remove credentials

### Messages
- `GET /messages/jobs` - List message jobs
- `GET /messages/jobs/{id}` - Get job details with attempts
- `POST /messages/send` - Send message with routing

### Admin
- `GET /admin/health` - Health check
- `GET /admin/metrics` - Prometheus metrics

## 🗄️ Database Schema

See `backend/app/models/models.py` for complete schema.

Key tables:
- `organization` - Organizations/tenants
- `user` - User accounts
- `organization_user` - User-org relationships
- `wa_connection` - WhatsApp Business API connections
- `message_event` - Message events from WA webhooks (includes baseline_cost_minor for savings calculation)
- `rate_card` - Pricing information
- `routing_rule` - Cost optimization rules
- `routed_action` - Actions taken by rules
- `economy_snapshot` - Aggregated savings data
- `provider` - Message providers (360dialog, Gupshup, etc)
- `provider_credential` - Encrypted credentials per org
- `message_job` - Message sending jobs with idempotency
- `delivery_attempt` - Delivery attempts with retry tracking
- `cost_record` - Cost tracking per message

## 🔐 Security Features

- JWT authentication with HS256
- Multi-tenant isolation by `org_id`
- WhatsApp tokens encrypted with Fernet
- Webhook idempotency via `provider_event_id`
- No message content stored (metadata only)

## 🛠️ Development

```bash
# Create migration
docker-compose exec api alembic revision --autogenerate -m "description"

# Run migration
docker-compose exec api alembic upgrade head

# Access database
docker-compose exec db psql -U postgres -d wa_cost_router

# Access Redis
docker-compose exec redis redis-cli

# Run worker manually
docker-compose exec worker python worker.py
```

## 📊 Sample Rate Card CSV

```csv
effective_from,country_iso,category,template_name,unit_cost_minor,currency,notes
2024-01-01T00:00:00Z,BR,MARKETING,,85,USD,Brazil marketing
2024-01-01T00:00:00Z,BR,UTILITY,,42,USD,Brazil utility
2024-01-01T00:00:00Z,ES,MARKETING,,95,USD,Spain marketing
2024-01-01T00:00:00Z,GLOBAL,MARKETING,,100,USD,Global fallback
```

## 🎯 Testing the API

```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123","org_name":"Test Org"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@demo.local","password":"demo123"}'

# Get current org (use token from login)
curl http://localhost:8000/orgs/current \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## 🔧 Environment Variables

See `.env.example` for all available configuration options.

## 📝 Notes

- Seed data is automatically loaded on first startup
- Access tokens are encrypted using Fernet (derived from APP_SECRET_KEY)
- Rate resolution: 1) template+country, 2) country+category, 3) GLOBAL+category
- Webhook events are deduplicated by `provider_event_id`

## 🐛 Troubleshooting

```bash
# Check service health
docker-compose ps

# View logs
docker-compose logs api
docker-compose logs db

# Restart services
docker-compose restart api

# Clean rebuild
docker-compose down -v
docker-compose up -d --build
```
