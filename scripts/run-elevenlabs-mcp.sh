#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ -z "${ELEVENLABS_API_KEY:-}" ]]; then
  echo "Error: ELEVENLABS_API_KEY is not set." >&2
  echo "Add it to $ENV_FILE or export it in your shell." >&2
  echo "Create a key at https://elevenlabs.io/app/settings/api-keys" >&2
  exit 1
fi

export ELEVENLABS_MCP_BASE_PATH="${ELEVENLABS_MCP_BASE_PATH:-$ROOT}"
export ELEVENLABS_MCP_OUTPUT_MODE="${ELEVENLABS_MCP_OUTPUT_MODE:-files}"

exec uvx elevenlabs-mcp
