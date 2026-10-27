#!/usr/bin/env bash
set -euo pipefail
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
DIR="$(dirname "$0")"
curl -fsSL "$API_BASE_URL/openapi.json" > "$DIR/../Garnix/Core/API/openapi.json"
