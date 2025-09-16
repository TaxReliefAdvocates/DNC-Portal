#!/usr/bin/env bash
set -euo pipefail

PORT_TO_USE="${PORT:-8000}"
echo "Starting Uvicorn on port ${PORT_TO_USE}"
exec python -m uvicorn do_not_call.main:app --host 0.0.0.0 --port "${PORT_TO_USE}" --log-level info


