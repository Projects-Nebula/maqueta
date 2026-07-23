#!/usr/bin/env bash
# Levanta el proyecto local: instala deps, prepara .env, migra, corre el server.
# Usa sqlite por defecto (sin Docker). Para Postgres: descomenta DATABASE_URL
# en .env y corré `docker compose up -d db` antes.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

command -v uv >/dev/null || { echo "Falta uv: https://docs.astral.sh/uv/"; exit 1; }
command -v npm >/dev/null || { echo "Falta npm/Node 20+ (para el build de Tailwind CSS)"; exit 1; }

if [ ! -f .env ]; then
  cp .env.example .env
  echo ".env creado desde .env.example — revisá los valores (AI_PROVIDER=fake por defecto)."
fi

uv sync
npm install
npm run build:css
# Para desarrollo activo del CSS: `npx @tailwindcss/cli -i static/editor/tailwind-input.css -o static/editor/tailwind.css --watch`
uv run python manage.py migrate
uv run python manage.py runserver 0.0.0.0:8000
