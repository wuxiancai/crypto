#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
PORT_ENV="$ROOT_DIR/.env.ports.generated"
REGENERATE_PORTS="${REGENERATE_PORTS:-0}"
RUNTIME_DIR="$ROOT_DIR/runtime"
LOG_DIR="$RUNTIME_DIR/logs"

mkdir -p "$RUNTIME_DIR" "$LOG_DIR"

if [[ ! -x "$VENV_PYTHON" ]]; then
  "$PYTHON_BIN" -m venv "$ROOT_DIR/.venv"
fi

"$VENV_PYTHON" -m ensurepip --upgrade >/dev/null
"$VENV_PYTHON" -m pip install -e . >/dev/null

if [[ "$REGENERATE_PORTS" == "1" || ! -f "$PORT_ENV" ]]; then
  "$VENV_PYTHON" -m app.deploy.ports
else
  echo "Using existing port config: ${PORT_ENV}"
fi

set -a
source "$PORT_ENV"
set +a

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi
  if sudo docker compose version >/dev/null 2>&1; then
    sudo docker compose "$@"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi
  if sudo docker-compose version >/dev/null 2>&1; then
    sudo docker-compose "$@"
    return
  fi

  echo "未找到 docker compose。请先安装 Docker Compose plugin。" >&2
  exit 1
}

POSTGRES_PORT="$POSTGRES_PORT" compose --env-file "$PORT_ENV" up -d --remove-orphans postgres

echo "Waiting for Postgres on port ${POSTGRES_PORT}..."
for _ in $(seq 1 40); do
  if "$VENV_PYTHON" - <<PY
import socket
sock = socket.socket()
sock.settimeout(1)
try:
    sock.connect(("127.0.0.1", int("${POSTGRES_PORT}")))
except OSError:
    raise SystemExit(1)
finally:
    sock.close()
PY
  then
    break
  fi
  sleep 2
done

DATABASE_URL="$DATABASE_URL" "$VENV_PYTHON" -m alembic upgrade head

pkill -f "scripts/run_paper_realtime.py" >/dev/null 2>&1 || true
pkill -f "scripts/run_paper_status_web.py" >/dev/null 2>&1 || true

nohup "$VENV_PYTHON" scripts/run_paper_realtime.py \
  --symbols BTCUSDT ETHUSDT \
  --intervals 5m 15m 1h 4h \
  --websocket-base-url "$BINANCE_WEBSOCKET_BASE_URL" \
  --state-path "$PAPER_STATE_PATH" \
  > "$LOG_DIR/paper-realtime.log" 2>&1 &

nohup "$VENV_PYTHON" scripts/run_paper_status_web.py \
  --host 0.0.0.0 \
  --port "$PAPER_WEB_PORT" \
  --state-path "$PAPER_STATE_PATH" \
  --error-log-path "$LOG_DIR/paper-realtime.log" \
  > "$LOG_DIR/paper-status-web.log" 2>&1 &

cat <<EOF
启动完成

Postgres 端口: ${POSTGRES_PORT}
Web 页面端口: ${PAPER_WEB_PORT}
Web 页面地址: http://服务器IP:${PAPER_WEB_PORT}
端口配置文件: ${PORT_ENV}
日志目录: ${LOG_DIR}
EOF
