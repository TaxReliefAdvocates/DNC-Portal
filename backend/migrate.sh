#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

CMD=${1:-}

if [[ "$CMD" == "revision" ]]; then
  shift || true
  alembic -c alembic.ini revision --autogenerate -m "${*:-auto}"
elif [[ "$CMD" == "upgrade" ]]; then
  alembic -c alembic.ini upgrade head
elif [[ "$CMD" == "downgrade" ]]; then
  alembic -c alembic.ini downgrade -1
else
  echo "Usage: $0 {revision [message] | upgrade | downgrade}"
fi


