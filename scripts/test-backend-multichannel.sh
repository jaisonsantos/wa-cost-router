#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
cd "${ROOT_DIR}" || exit 1

# Ensure sandbox defaults for email/SMS connectors so pytest can rely on deterministic providers.
export SANDBOX_PROVIDERS="${SANDBOX_PROVIDERS:-true}"
export SANDBOX_LATENCY_MS="${SANDBOX_LATENCY_MS:-0}"
export SANDBOX_FAILURE_RATE="${SANDBOX_FAILURE_RATE:-0}"

export SENDGRID_API_KEY="${SENDGRID_API_KEY:-sandbox-sendgrid-api-key}"
export SENDGRID_DEFAULT_SENDER_EMAIL="${SENDGRID_DEFAULT_SENDER_EMAIL:-no-reply+sandbox@example.com}"
export SENDGRID_BASE_URL="${SENDGRID_BASE_URL:-https://api.sendgrid.com/v3}"

export TWILIO_ACCOUNT_SID="${TWILIO_ACCOUNT_SID:-AC00000000000000000000000000000000}"
export TWILIO_AUTH_TOKEN="${TWILIO_AUTH_TOKEN:-sandbox-twilio-auth-token}"
export TWILIO_FROM_NUMBER="${TWILIO_FROM_NUMBER:-+15558675309}"
export TWILIO_MESSAGING_SERVICE_SID="${TWILIO_MESSAGING_SERVICE_SID:-MG00000000000000000000000000000000}"

PYTEST_TARGETS=(
  "backend/tests/test_messages_api.py"
  "backend/tests/test_integrations_email.py"
  "backend/tests/test_integrations_sms.py"
  "backend/tests/test_sendgrid_connector.py"
  "backend/tests/test_webhook_email_events.py"
  "backend/tests/test_webhook_sms_events.py"
  "backend/tests/test_sandbox_connectors.py"
  "backend/tests/services/test_routing_engine_channels.py"
)

if ! command -v pytest >/dev/null 2>&1; then
  echo "pytest não encontrado no PATH. Ative seu ambiente virtual antes de rodar os testes." >&2
  exit 127
fi

pytest "${PYTEST_TARGETS[@]}"
