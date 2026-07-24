#!/usr/bin/env bash
# Levanta el proyecto local: instala deps, prepara .env, migra, corre el server.
# PostgreSQL es la base local oficial; si DATABASE_URL apunta a PostgreSQL,
# levanta y espera automáticamente el servicio db de Docker Compose.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

command -v uv >/dev/null || { echo "Falta uv: https://docs.astral.sh/uv/"; exit 1; }
command -v pnpm >/dev/null || { echo "Falta pnpm/Node 20+; ejecutá 'corepack enable pnpm' (para el build de Tailwind CSS)"; exit 1; }

if [ ! -f .env ]; then
  cp .env.example .env
  echo ".env creado desde .env.example — revisá los valores (PostgreSQL local y AI_PROVIDER=fake por defecto)."
fi

port="${PORT:-8000}"
if ! [[ "$port" =~ ^[0-9]+$ ]] || (( port < 1 || port > 65535 )); then
  echo "PORT debe ser un número entre 1 y 65535 (valor recibido: $port)." >&2
  exit 1
fi
if command -v ss >/dev/null && ss -ltn "sport = :$port" | grep 'LISTEN' >/dev/null; then
  echo "El puerto $port ya está en uso; el servidor probablemente ya está levantado." >&2
  echo "Detené la instancia existente o probá con PORT=8001 ./run-local.sh." >&2
  exit 1
fi

database_url="$(awk -F= '$1 == "DATABASE_URL" { value = substr($0, index($0, "=") + 1) } END { print value }' .env)"
database_url="${database_url//\"/}"
database_url="${database_url//\'/}"
case "$database_url" in
  postgres://*|postgresql://*)
    command -v docker >/dev/null || {
      echo "Falta Docker: PostgreSQL está configurado en DATABASE_URL." >&2
      exit 1
    }
    docker compose version >/dev/null 2>&1 || {
      echo "Falta Docker Compose: PostgreSQL está configurado en DATABASE_URL." >&2
      exit 1
    }
    echo "Levantando PostgreSQL y esperando que esté saludable..."
    docker compose up -d --wait db
    ;;
esac

uv sync
pnpm install --frozen-lockfile
pnpm run build:css
# Para desarrollo activo del CSS: `pnpm exec @tailwindcss/cli -i static/editor/tailwind-input.css -o static/editor/tailwind.css --watch`
uv run python manage.py migrate
uv run python manage.py runserver "0.0.0.0:$port"
