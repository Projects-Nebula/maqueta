#!/usr/bin/env bash
# Detiene el runserver local; con --db también detiene PostgreSQL sin borrar el volumen.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if (( $# > 1 )); then
  echo "Uso: PORT=8000 ./stop-local.sh [--db]" >&2
  exit 1
fi

port="${PORT:-8000}"
if ! [[ "$port" =~ ^[0-9]+$ ]] || (( port < 1 || port > 65535 )); then
  echo "PORT debe ser un número entre 1 y 65535 (valor recibido: $port)." >&2
  exit 1
fi

stop_db=false
case "${1:-}" in
  "") ;;
  --db) stop_db=true ;;
  -h|--help)
    echo "Uso: PORT=8000 ./stop-local.sh [--db]"
    echo "  --db  también detiene el contenedor PostgreSQL sin eliminar sus datos"
    exit 0
    ;;
  *)
    echo "Argumento desconocido: $1" >&2
    echo "Uso: PORT=8000 ./stop-local.sh [--db]" >&2
    exit 1
    ;;
esac

command -v pgrep >/dev/null || {
  echo "Falta pgrep (paquete procps) para localizar el runserver." >&2
  exit 1
}

pattern="manage.py runserver 0.0.0.0:${port}"
mapfile -t server_pids < <(pgrep -f "$pattern" || true)

if ((${#server_pids[@]} == 0)); then
  echo "No encontré un runserver local en el puerto $port."
else
  echo "Deteniendo Django en el puerto $port (PID: ${server_pids[*]})..."
  kill -TERM "${server_pids[@]}" 2>/dev/null || true

  for _ in {1..20}; do
    if ! pgrep -f "$pattern" >/dev/null; then
      break
    fi
    sleep 0.25
  done

  mapfile -t remaining_pids < <(pgrep -f "$pattern" || true)
  if ((${#remaining_pids[@]} > 0)); then
    echo "El proceso no terminó a tiempo; enviando SIGKILL..." >&2
    kill -KILL "${remaining_pids[@]}" 2>/dev/null || true
  fi
  echo "Django detenido."
fi

if [[ "$stop_db" == true ]]; then
  command -v docker >/dev/null || {
    echo "Falta Docker para detener PostgreSQL." >&2
    exit 1
  }
  docker compose version >/dev/null 2>&1 || {
    echo "Falta Docker Compose para detener PostgreSQL." >&2
    exit 1
  }
  echo "Deteniendo PostgreSQL (el volumen se conserva)..."
  docker compose stop db
else
  echo "PostgreSQL queda encendido. Usá --db para detener también el contenedor."
fi
