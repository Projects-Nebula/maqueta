#!/usr/bin/env bash
# Reset the local development database and load deterministic demo data.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

command -v uv >/dev/null || {
  echo "Missing uv: https://docs.astral.sh/uv/" >&2
  exit 1
}

if [ ! -f .env ]; then
  cp .env.example .env
  echo ".env created from .env.example."
fi

database_url="$(awk -F= '$1 == "DATABASE_URL" { value = substr($0, index($0, "=") + 1) } END { print value }' .env)"
database_url="${database_url//\"/}"
database_url="${database_url//\'/}"
case "$database_url" in
  postgres://*|postgresql://*)
    command -v docker >/dev/null || {
      echo "Missing Docker: PostgreSQL is configured in DATABASE_URL." >&2
      exit 1
    }
    docker compose version >/dev/null 2>&1 || {
      echo "Missing Docker Compose: PostgreSQL is configured in DATABASE_URL." >&2
      exit 1
    }
    echo "Starting PostgreSQL and waiting for it to become healthy..."
    docker compose up -d --wait db
    ;;
esac

echo "Applying migrations before the destructive local reset..."
uv run python manage.py migrate --noinput
uv run python manage.py mockup_data "$@"
