Task 3 — Customer Portal (Stripe) backend + botão na UI

Branch: feat/billing-customer-portal

What was done:
- Added backend endpoint `GET /billing/portal` in `backend/app/api/billing.py`.
- Extended Stripe gateway with `create_billing_portal_session` in `backend/app/services/billing/stripe_client.py`.
- Added backend tests `backend/tests/test_billing_portal.py`.
- Added frontend API method `createBillingPortal` in `src/lib/api.ts` and hook `useCreateBillingPortal` in `src/hooks/useApi.ts`.
- Updated `src/pages/Settings.tsx` adding "Gerenciar assinatura" button and handling loading/errors.
- Added Playwright E2E test `tests/e2e/billing-portal.spec.ts` that mocks portal URL and validates navigation.
- Updated `docs/api/API_REFERENCE.md` and `README.md` with billing portal docs and env vars.

Notes / Migration:
- No DB migration required.
- Ensure `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` are set in `backend/.env` to enable flows.

Validation steps:
- Run backend tests: `make test-backend` (or `pytest backend/tests -q`).
- Run frontend e2e: `npm run test:e2e` (Playwright) with stack running.

