#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
cd "${ROOT_DIR}" || exit 1

if ! command -v npm >/dev/null 2>&1; then
  echo "npm não encontrado no PATH. Instale Node.js 20+ antes de continuar." >&2
  exit 127
fi

API_BASE_URL="${E2E_API_BASE_URL:-http://localhost:8000}"
HEALTH_URL="${E2E_API_HEALTH_URL:-${API_BASE_URL%/}/admin/health}"

# Ensure sandbox defaults to avoid hitting external providers during Playwright flows.
export SANDBOX_PROVIDERS="${SANDBOX_PROVIDERS:-true}"
export SANDBOX_LATENCY_MS="${SANDBOX_LATENCY_MS:-0}"
export SANDBOX_FAILURE_RATE="${SANDBOX_FAILURE_RATE:-0}"

export SENDGRID_API_KEY="${SENDGRID_API_KEY:-sandbox-sendgrid-api-key}"
export SENDGRID_DEFAULT_SENDER_EMAIL="${SENDGRID_DEFAULT_SENDER_EMAIL:-no-reply+sandbox@example.com}"
export TWILIO_ACCOUNT_SID="${TWILIO_ACCOUNT_SID:-AC00000000000000000000000000000000}"
export TWILIO_AUTH_TOKEN="${TWILIO_AUTH_TOKEN:-sandbox-twilio-auth-token}"
export TWILIO_FROM_NUMBER="${TWILIO_FROM_NUMBER:-+15558675309}"
export TWILIO_MESSAGING_SERVICE_SID="${TWILIO_MESSAGING_SERVICE_SID:-MG00000000000000000000000000000000}"

if [ ! -d "node_modules" ]; then
  echo "node_modules não encontrado. Execute 'npm install' ou 'npm ci' antes dos testes." >&2
  exit 1
fi

if [ "${SKIP_PLAYWRIGHT_INSTALL:-0}" != "1" ]; then
  INSTALL_ARGS="${PLAYWRIGHT_INSTALL_ARGS:-}";
  if [ -z "${INSTALL_ARGS}" ] && [ "${CI:-}" = "true" ]; then
    INSTALL_ARGS="--with-deps"
  fi
  npx playwright install ${INSTALL_ARGS}
fi

printf "Verificando saúde da API em %s...\n" "${HEALTH_URL}"
ready=0
for attempt in $(seq 1 20); do
  status=$(curl -s -o /dev/null -w '%{http_code}' "${HEALTH_URL}" || true)
  if [ "${status}" = "200" ]; then
    ready=1
    break
  fi
  printf "  tentativa %s - status %s\n" "${attempt}" "${status:-N/A}"
  sleep 2
done

if [ "${ready}" -ne 1 ]; then
  echo "API não respondeu 200 em ${HEALTH_URL}. Garanta que 'make dev' ou 'make ci-e2e' esteja ativo." >&2
  exit 1
fi

E2E_API_BASE_URL="${API_BASE_URL}" npm run test:e2e
