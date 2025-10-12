#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
cd "${ROOT_DIR}" || exit 1

if ! command -v npm >/dev/null 2>&1; then
  echo "npm não encontrado no PATH. Instale Node.js 20+ antes de continuar." >&2
  exit 127
fi

export CI="${CI:-true}"

if [ ! -d "node_modules" ]; then
  echo "node_modules não encontrado. Execute 'npm install' ou 'npm ci' antes dos testes." >&2
  exit 1
fi

npm run test
