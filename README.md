# WA Cost Router

WA Cost Router is a multi-tenant messaging platform that routes WhatsApp, SMS, and email traffic with a strong focus on cost control, provider abstraction, billing, and operational visibility.

The project combines a FastAPI backend, asynchronous workers, PostgreSQL, Redis, Stripe billing, and a React frontend in a sandbox-friendly local environment.

## Why this project

Messaging products often need to coordinate multiple providers, retries, tenant isolation, usage metering, webhooks, and billing. WA Cost Router brings those concerns into one system while keeping provider integrations replaceable and testable.

## Engineering highlights

- **Multi-tenant backend** with organization-scoped data and provider configuration.
- **Provider abstraction** for WhatsApp, SMS, and email flows.
- **Asynchronous processing** with Redis and RQ workers.
- **Stripe billing** with checkout, customer portal, usage synchronization, invoice reconciliation, automatic tax support, and usage metrics.
- **Observability** through Prometheus-style metrics and structured operational signals.
- **Resilience** with retries and exponential backoff for background jobs.
- **Sandbox providers** for deterministic local development and CI.
- **API and UI coverage** with Pytest, Postman/Newman, and Playwright end-to-end tests.
- **CI/CD** through GitHub Actions, plus a local lightweight fallback pipeline.
- **Automated CI remediation workflow** that can invoke Codex after CI failures, apply a minimal patch, rerun checks, and open a reviewable PR when configured.

## Architecture

```text
                   ┌─────────────────┐
                   │   React / Vite  │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │     FastAPI     │
                   │ auth / routing  │
                   │ billing / APIs  │
                   └───────┬─────────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
        PostgreSQL       Redis / RQ     Stripe
                             │
                             ▼
                       Async workers
                             │
                ┌────────────┼────────────┐
                ▼            ▼            ▼
             WhatsApp       SMS         Email
```

## Core capabilities

- Organization and tenant-scoped configuration.
- Messaging-provider forms exposed through the API.
- Sandbox message delivery for repeatable development and testing.
- Background usage publication and reconciliation jobs.
- Stripe checkout and customer portal flows.
- Usage and billing metrics by organization.
- Retry and failure handling for asynchronous jobs.
- Postman collection and Newman automation.
- End-to-end browser tests with Playwright.

## Tech stack

- **Backend:** FastAPI, SQLAlchemy, Alembic
- **Database:** PostgreSQL 16
- **Queues / cache:** Redis 7, RQ
- **Frontend:** React, Vite
- **Billing:** Stripe
- **Testing:** Pytest, Postman/Newman, Playwright
- **CI/CD:** GitHub Actions, Docker Compose

## Quick start

```bash
cp backend/.env.example backend/.env
make dev
```

The default development configuration enables sandbox providers so local runs and automated tests do not need live messaging credentials.

Useful commands:

```bash
make migrate
make seed
make lint-backend
make test-backend
make postman-test
npm run test:e2e
make down
```

## Billing

Live Stripe functionality is enabled through environment variables such as:

```env
STRIPE_SECRET_KEY=<your-stripe-secret-key>
STRIPE_WEBHOOK_SECRET=<your-webhook-signing-secret>
```

When billing credentials are absent, endpoints that depend on Stripe fail explicitly instead of silently using embedded credentials.

The billing workers support usage aggregation, retries with exponential backoff, and reconciliation between local invoice state and Stripe.

## Testing strategy

The repository includes several layers of verification:

- **Backend:** Ruff + Pytest.
- **API workflows:** Postman/Newman.
- **Browser flows:** Playwright.
- **CI:** backend, frontend, and end-to-end jobs.
- **Local fallback:** `make ci-lite` for environments where GitHub Actions is unavailable.

## CI-assisted remediation

When configured with the required repository secret, `codex-autofix.yml` can react to failed CI runs. The workflow checks out the failing branch, asks Codex for a constrained patch, reruns tests, and opens a temporary PR only when the remediation succeeds.

This keeps the AI-assisted workflow reviewable rather than pushing generated changes directly to the main branch.

## Documentation

Detailed operational and product documentation lives under `docs/`:

- [`docs/api/API_REFERENCE.md`](docs/api/API_REFERENCE.md)
- [`docs/postman/README.md`](docs/postman/README.md)
- [`docs/backlog/README.md`](docs/backlog/README.md)
- [`docs/current-cycle/README.md`](docs/current-cycle/README.md)
- [`docs/operations/OPERATIONS.md`](docs/operations/OPERATIONS.md)
- [`docs/runbooks/ci_billing.md`](docs/runbooks/ci_billing.md)

## Security note

Development credentials in examples and sandbox files are placeholders only. Real provider, webhook, and billing secrets belong in local environment files or repository secrets and must not be committed.

## License

MIT
