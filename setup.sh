#!/usr/bin/env bash
# Verifica e instala, con confirmación, los requisitos para ejecutar el proyecto.
# No inicia Django: al finalizar, usá ./run-local.sh.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

readonly REQUIRED_NODE_MAJOR=20
readonly REQUIRED_PNPM_VERSION="10.33.2"
readonly NVM_VERSION="v0.40.3"

PNPM_CMD=(pnpm)

abort() {
  printf 'Setup detenido: %s\n' "$1" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Uso: ./setup.sh

Verifica los requisitos locales, pregunta antes de instalar los que falten,
prepara las dependencias del proyecto, compila Tailwind, inicia PostgreSQL
si está configurado y aplica las migraciones.

El servidor Django no se inicia desde este script. Usá ./run-local.sh al final.
EOF
}

ask_yes_no() {
  local prompt="${1:?missing prompt}" answer

  if [[ ! -t 0 ]]; then
    printf 'No puedo pedir confirmación porque la entrada no es interactiva.\n' >&2
    return 1
  fi

  while true; do
    read -r -p "$prompt [s/N] " answer || return 1
    case "${answer,,}" in
      s|si|sí|y|yes) return 0 ;;
      ''|n|no) return 1 ;;
      *) printf 'Respondé s o n.\n' ;;
    esac
  done
}

run_privileged() {
  if (( EUID == 0 )); then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    abort "necesito sudo o permisos de root para ejecutar: $*"
  fi
}

apt_install() {
  run_privileged apt-get update
  run_privileged apt-get install -y "$@"
}

install_curl() {
  case "$(uname -s)" in
    Darwin)
      command -v brew >/dev/null 2>&1 || abort "no encontré Homebrew para instalar curl"
      brew install curl
      ;;
    Linux)
      if command -v apt-get >/dev/null 2>&1; then
        apt_install curl
      elif command -v dnf >/dev/null 2>&1; then
        run_privileged dnf install -y curl
      elif command -v pacman >/dev/null 2>&1; then
        run_privileged pacman -Sy --noconfirm curl
      else
        abort "no reconozco un gestor de paquetes para instalar curl"
      fi
      ;;
    *)
      abort "sistema operativo no soportado para instalar curl automáticamente"
      ;;
  esac
}

ensure_curl() {
  command -v curl >/dev/null 2>&1 && return 0

  printf 'Falta curl, necesario para instalar uv o Node.js mediante nvm.\n'
  ask_yes_no '¿Querés instalar curl?' || abort 'curl es necesario para continuar'
  install_curl
  command -v curl >/dev/null 2>&1 || abort 'curl no quedó disponible después de la instalación'
}

ensure_uv() {
  command -v uv >/dev/null 2>&1 && return 0

  printf 'No encontré uv, el gestor de Python requerido por el proyecto.\n'
  ask_yes_no '¿Querés instalar uv desde el instalador oficial?' || abort 'uv es necesario para continuar'
  ensure_curl
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  command -v uv >/dev/null 2>&1 || abort 'uv se instaló, pero no está disponible en el PATH actual'
}

node_is_ready() {
  local major

  command -v node >/dev/null 2>&1 || return 1
  major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || true)"
  [[ "$major" =~ ^[0-9]+$ ]] && (( major >= REQUIRED_NODE_MAJOR ))
}

install_node_with_nvm() {
  local nvm_dir="${NVM_DIR:-$HOME/.nvm}"

  ensure_curl
  export NVM_DIR="$nvm_dir"
  if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
    curl -fsSL "https://raw.githubusercontent.com/nvm-sh/nvm/${NVM_VERSION}/install.sh" | bash
  fi
  [[ -s "$NVM_DIR/nvm.sh" ]] || abort 'nvm no quedó disponible después de la instalación'

  # nvm is not guaranteed to be nounset-safe while loading.
  set +u
  # shellcheck disable=SC1090
  source "$NVM_DIR/nvm.sh"
  set -u
  nvm install 20
  nvm alias default 20
  nvm use 20
  hash -r
}

ensure_node() {
  node_is_ready && return 0

  if command -v node >/dev/null 2>&1; then
    printf 'Encontré Node.js %s, pero Tailwind requiere Node.js %s o superior.\n' \
      "$(node --version 2>/dev/null || printf 'desconocido')" "$REQUIRED_NODE_MAJOR"
  else
    printf 'No encontré Node.js; Tailwind requiere Node.js %s o superior.\n' "$REQUIRED_NODE_MAJOR"
  fi
  ask_yes_no '¿Querés instalar Node.js 20 mediante nvm?' || abort 'Node.js 20+ es necesario para continuar'
  install_node_with_nvm
  node_is_ready || abort 'Node.js 20+ no quedó disponible en el PATH actual'
}

pnpm_is_ready() {
  local version

  command -v pnpm >/dev/null 2>&1 || return 1
  version="$(pnpm --version 2>/dev/null || true)"
  [[ "$version" == "$REQUIRED_PNPM_VERSION" ]]
}

ensure_pnpm() {
  pnpm_is_ready && return 0

  if command -v pnpm >/dev/null 2>&1; then
    printf 'Encontré pnpm %s, pero el proyecto requiere pnpm %s.\n' \
      "$(pnpm --version 2>/dev/null || printf 'desconocido')" "$REQUIRED_PNPM_VERSION"
  else
    printf 'No encontré pnpm %s, el gestor de paquetes frontend requerido.\n' "$REQUIRED_PNPM_VERSION"
  fi
  ask_yes_no "¿Querés instalar/configurar pnpm $REQUIRED_PNPM_VERSION?" || abort 'pnpm es necesario para continuar'

  if command -v corepack >/dev/null 2>&1; then
    corepack enable pnpm || true
    if ! corepack install --global "pnpm@$REQUIRED_PNPM_VERSION"; then
      corepack prepare "pnpm@$REQUIRED_PNPM_VERSION" --activate
    fi
  elif command -v npm >/dev/null 2>&1; then
    # Solo se usa como mecanismo de bootstrap cuando Node no incluye Corepack.
    npm install --global "pnpm@$REQUIRED_PNPM_VERSION"
  else
    abort 'Node.js no incluye Corepack y npm tampoco está disponible para instalar pnpm'
  fi
  hash -r

  if pnpm_is_ready; then
    PNPM_CMD=(pnpm)
  elif command -v corepack >/dev/null 2>&1 \
    && [[ "$(corepack pnpm --version 2>/dev/null || true)" == "$REQUIRED_PNPM_VERSION" ]]; then
    PNPM_CMD=(corepack pnpm)
  else
    abort "pnpm $REQUIRED_PNPM_VERSION no quedó disponible en el PATH actual"
  fi
}

ensure_python_version() {
  uv python find 3.12 >/dev/null 2>&1 && return 0

  printf 'No encontré Python 3.12, requerido por pyproject.toml.\n'
  ask_yes_no '¿Querés que uv instale Python 3.12?' || abort 'Python 3.12 es necesario para continuar'
  uv python install 3.12
  uv python find 3.12 >/dev/null 2>&1 || abort 'Python 3.12 no quedó disponible para uv'
}

install_docker() {
  case "$(uname -s)" in
    Darwin)
      command -v brew >/dev/null 2>&1 || abort 'no encontré Homebrew para instalar Docker Desktop'
      brew install --cask docker
      ;;
    Linux)
      if command -v apt-get >/dev/null 2>&1; then
        if ! apt_install docker.io docker-compose-v2 \
          && ! apt_install docker.io docker-compose-plugin \
          && ! apt_install docker.io docker-compose; then
          abort 'no pude instalar Docker y Docker Compose con apt'
        fi
      elif command -v dnf >/dev/null 2>&1; then
        run_privileged dnf install -y docker docker-compose-plugin
      elif command -v pacman >/dev/null 2>&1; then
        run_privileged pacman -Sy --noconfirm docker docker-compose
      else
        abort 'no reconozco un gestor de paquetes para instalar Docker'
      fi
      ;;
    *)
      abort 'sistema operativo no soportado para instalar Docker automáticamente'
      ;;
  esac
}

ensure_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    printf 'No encontré Docker, necesario porque DATABASE_URL usa PostgreSQL.\n'
    ask_yes_no '¿Querés instalar Docker y Docker Compose?' || abort 'Docker es necesario para PostgreSQL local'
    install_docker
  fi
  command -v docker >/dev/null 2>&1 || abort 'Docker no quedó disponible en el PATH actual'

  if ! docker compose version >/dev/null 2>&1; then
    printf 'Docker está instalado, pero no encontré el subcomando Docker Compose v2.\n'
    ask_yes_no '¿Querés instalar el complemento de Docker Compose?' \
      || abort 'Docker Compose v2 es necesario para PostgreSQL local'
    case "$(uname -s)" in
      Linux)
        if command -v apt-get >/dev/null 2>&1; then
          if ! apt_install docker-compose-v2 \
            && ! apt_install docker-compose-plugin \
            && ! apt_install docker-compose; then
            abort 'no pude instalar Docker Compose con el gestor de paquetes disponible'
          fi
        elif command -v dnf >/dev/null 2>&1; then
          run_privileged dnf install -y docker-compose-plugin
        elif command -v pacman >/dev/null 2>&1; then
          run_privileged pacman -Sy --noconfirm docker-compose
        else
          abort 'no reconozco un gestor de paquetes para instalar Docker Compose'
        fi
        ;;
      Darwin)
        command -v brew >/dev/null 2>&1 || abort 'no encontré Homebrew para instalar Docker Compose'
        brew install docker-compose
        ;;
      *)
        abort 'sistema operativo no soportado para instalar Docker Compose automáticamente'
        ;;
    esac
  fi
  docker compose version >/dev/null 2>&1 || abort 'Docker Compose v2 no quedó disponible'

  if ! docker info >/dev/null 2>&1; then
    printf 'Docker está instalado, pero el daemon no está respondiendo.\n'
    if ! ask_yes_no '¿Querés que intente iniciar el daemon de Docker?'; then
      abort 'iniciá Docker y ejecutá setup.sh nuevamente'
    fi
    if command -v systemctl >/dev/null 2>&1; then
      run_privileged systemctl start docker || true
    elif command -v service >/dev/null 2>&1; then
      run_privileged service docker start || true
    else
      printf 'Iniciá Docker Desktop manualmente y ejecutá setup.sh nuevamente.\n' >&2
    fi
  fi
  docker info >/dev/null 2>&1 || abort 'el daemon de Docker sigue sin responder'
}

ensure_env() {
  [[ -f .env ]] && return 0
  [[ -f .env.example ]] || abort 'falta .env.example para crear la configuración local'

  printf 'No existe .env, necesario para ejecutar Django y conectar PostgreSQL.\n'
  ask_yes_no '¿Querés crear .env desde .env.example?' || abort 'sin .env no se puede continuar'
  cp .env.example .env
  printf '.env creado. Revisá sus valores antes de usar proveedores reales.\n'
}

database_url_from_env() {
  local value

  value="$(awk -F= '$1 == "DATABASE_URL" { value = substr($0, index($0, "=") + 1) } END { print value }' .env)"
  value="${value//\"/}"
  value="${value//\'/}"
  printf '%s' "$value"
}

ensure_dependencies() {
  local python_ready=false
  local node_ready=false

  if [[ -x .venv/bin/python ]] && .venv/bin/python -c 'import django, psycopg' >/dev/null 2>&1; then
    python_ready=true
  fi
  if [[ -x node_modules/.bin/tailwindcss ]] && [[ -x node_modules/.bin/playwright ]]; then
    node_ready=true
  fi

  if [[ "$python_ready" == true && "$node_ready" == true ]]; then
    printf 'Dependencias Python y Node ya están disponibles.\n'
    return 0
  fi

  printf 'Faltan dependencias del proyecto o no están completas.\n'
  ask_yes_no '¿Querés instalar/sincronizar las dependencias ahora?' \
    || abort 'las dependencias del proyecto son necesarias para continuar'
  uv sync --frozen
  "${PNPM_CMD[@]}" install --frozen-lockfile
}

ensure_postgres() {
  local container_id health

  ensure_docker
  docker compose config --quiet
  container_id="$(docker compose ps -q db 2>/dev/null || true)"
  health=''
  if [[ -n "$container_id" ]]; then
    health="$(docker inspect --format '{{.State.Health.Status}}' "$container_id" 2>/dev/null || true)"
  fi

  if [[ "$health" == healthy ]]; then
    printf 'PostgreSQL ya está saludable.\n'
    return 0
  fi

  printf 'PostgreSQL no está saludable o todavía no fue iniciado.\n'
  ask_yes_no '¿Querés levantar PostgreSQL con Docker Compose?' \
    || abort 'PostgreSQL es necesario para continuar con la configuración local'
  docker compose up -d --wait db || abort 'no pude levantar PostgreSQL con Docker Compose'
}

main() {
  case "${1:-}" in
    '') ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; abort "argumento desconocido: $1" ;;
  esac

  printf 'Verificando requisitos de maqueta...\n'
  ensure_uv
  ensure_python_version
  ensure_node
  ensure_pnpm
  ensure_env

  database_url="$(database_url_from_env)"
  case "$database_url" in
    postgres://*|postgresql://*)
      ensure_postgres
      ;;
    sqlite://*)
      printf 'DATABASE_URL usa SQLite explícitamente; se omite Docker/PostgreSQL.\n'
      ;;
    '')
      abort 'DATABASE_URL no está definido en .env'
      ;;
    *)
      abort "DATABASE_URL usa un esquema no soportado: ${database_url%%:*}"
      ;;
  esac

  ensure_dependencies
  "${PNPM_CMD[@]}" run build:css
  uv run python manage.py migrate --noinput

  printf '\nSetup completado. Ejecutá ./run-local.sh para iniciar Django.\n'
}

main "$@"
