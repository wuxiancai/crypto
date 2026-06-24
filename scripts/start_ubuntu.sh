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

stop_process_by_pattern() {
  local label="$1"
  local pattern="$2"
  local pids

  pids="$(pgrep -f "$pattern" || true)"
  if [[ -z "$pids" ]]; then
    return
  fi

  echo "检测到已运行的 ${label}，先停止: ${pids//$'\n'/ }"
  kill $pids >/dev/null 2>&1 || true

  for _ in $(seq 1 10); do
    if ! pgrep -f "$pattern" >/dev/null 2>&1; then
      return
    fi
    sleep 1
  done

  pids="$(pgrep -f "$pattern" || true)"
  if [[ -n "$pids" ]]; then
    echo "${label} 未在超时时间内退出，执行强制停止: ${pids//$'\n'/ }"
    kill -9 $pids >/dev/null 2>&1 || true
  fi
}

stop_existing_project() {
  echo "检查是否已有项目进程在运行..."
  stop_process_by_pattern "Paper 实时交易进程" "scripts/run_paper_realtime.py"
  stop_process_by_pattern "Paper Web 状态页进程" "scripts/run_paper_status_web.py"
  POSTGRES_PORT="$POSTGRES_PORT" compose --env-file "$PORT_ENV" stop postgres >/dev/null 2>&1 || true
}

stop_existing_project

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
