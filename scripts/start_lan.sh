#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
PORT_ENV="$ROOT_DIR/.env.ports.generated"
REGENERATE_PORTS="${REGENERATE_PORTS:-0}"
START_MODE="${START_MODE:-background}"
KLINE_SYNC_LIMIT="${KLINE_SYNC_LIMIT:-800}"
PAPER_WEB_HOST="${PAPER_WEB_HOST:-0.0.0.0}"
RUNTIME_DIR="$ROOT_DIR/runtime"
LOG_DIR="$RUNTIME_DIR/logs"
PAPER_REALTIME_PID=""
PAPER_WEB_PID=""

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
  # Backfill Postgres credentials for env files generated before they were required.
  "$VENV_PYTHON" -c "from pathlib import Path; from app.deploy.ports import backfill_credentials_env; backfill_credentials_env(Path('${PORT_ENV}'))"
fi

set -a
source "$PORT_ENV"
set +a

compose() {
  if docker info >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi
  if sudo docker info >/dev/null 2>&1 && sudo docker compose version >/dev/null 2>&1; then
    sudo docker compose "$@"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1 && sudo docker-compose version >/dev/null 2>&1; then
    sudo docker-compose "$@"
    return
  fi

  docker_user="${SUDO_USER:-$(whoami)}"
  echo "无法访问 Docker。请确认 Docker 已启动，并且当前用户在 docker 组，或当前用户可以执行 sudo docker。" >&2
  echo "可临时执行：sudo bash scripts/start_lan.sh" >&2
  echo "可永久修复：sudo usermod -aG docker ${docker_user} 后重新登录。" >&2
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

if ! DATABASE_URL="$DATABASE_URL" "$VENV_PYTHON" -m alembic upgrade head; then
  cat >&2 <<EOF

数据库连接或迁移失败。

如果错误是 "password authentication failed for user crypto"，通常表示：
  - 当前 .env.ports.generated 里的 POSTGRES_PASSWORD
  - 与已有 Docker Postgres 数据卷初始化时的密码不一致。

局域网测试环境若不需要保留旧数据库，可执行：
  docker compose --env-file .env.ports.generated down -v
  rm -f .env.ports.generated runtime/paper-state.json
  bash scripts/start_lan.sh

或者使用局域网部署脚本一键重置：
  DEPLOY_DATABASE_MODE=reset bash scripts/deploy_ubuntu_lan.sh

如果需要保留旧数据库，必须找回旧的 .env.ports.generated / POSTGRES_PASSWORD，
让 DATABASE_URL 使用旧数据库真实密码。

EOF
  exit 1
fi

sync_required_klines() {
  echo "检查并补齐策略所需 K 线数据..."
  DATABASE_URL="$DATABASE_URL" "$VENV_PYTHON" scripts/sync_klines.py \
    --symbols BTCUSDT ETHUSDT \
    --intervals 1d 4h 1h 15m \
    --limit "$KLINE_SYNC_LIMIT" \
    --write
}

sync_required_klines

start_paper_realtime() {
  if [[ "$START_MODE" == "foreground" ]]; then
    "$VENV_PYTHON" scripts/run_paper_realtime.py \
      --symbols BTCUSDT ETHUSDT \
      --intervals 5m 15m 1h 4h 1d \
      --enable-layered-strategy \
      --websocket-base-url "$BINANCE_WEBSOCKET_BASE_URL" \
      --state-path "$PAPER_STATE_PATH" \
      >> "$LOG_DIR/paper-realtime.log" 2>&1 &
  else
    nohup "$VENV_PYTHON" scripts/run_paper_realtime.py \
      --symbols BTCUSDT ETHUSDT \
      --intervals 5m 15m 1h 4h 1d \
      --enable-layered-strategy \
      --websocket-base-url "$BINANCE_WEBSOCKET_BASE_URL" \
      --state-path "$PAPER_STATE_PATH" \
      > "$LOG_DIR/paper-realtime.log" 2>&1 &
  fi
  PAPER_REALTIME_PID="$!"
  echo "$PAPER_REALTIME_PID" > "$RUNTIME_DIR/paper-realtime.pid"
}

start_paper_status_web() {
  if [[ "$START_MODE" == "foreground" ]]; then
    "$VENV_PYTHON" scripts/run_paper_status_web.py \
      --host "$PAPER_WEB_HOST" \
      --port "$PAPER_WEB_PORT" \
      --state-path "$PAPER_STATE_PATH" \
      --error-log-path "$LOG_DIR/paper-realtime.log" \
      >> "$LOG_DIR/paper-status-web.log" 2>&1 &
  else
    nohup "$VENV_PYTHON" scripts/run_paper_status_web.py \
      --host "$PAPER_WEB_HOST" \
      --port "$PAPER_WEB_PORT" \
      --state-path "$PAPER_STATE_PATH" \
      --error-log-path "$LOG_DIR/paper-realtime.log" \
      > "$LOG_DIR/paper-status-web.log" 2>&1 &
  fi
  PAPER_WEB_PID="$!"
  echo "$PAPER_WEB_PID" > "$RUNTIME_DIR/paper-status-web.pid"
}

cleanup_foreground() {
  echo "Stopping crypto paper services..."
  if [[ -n "$PAPER_REALTIME_PID" ]]; then
    kill "$PAPER_REALTIME_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$PAPER_WEB_PID" ]]; then
    kill "$PAPER_WEB_PID" >/dev/null 2>&1 || true
  fi
  wait "$PAPER_REALTIME_PID" "$PAPER_WEB_PID" >/dev/null 2>&1 || true
  POSTGRES_PORT="$POSTGRES_PORT" compose --env-file "$PORT_ENV" stop postgres >/dev/null 2>&1 || true
}

start_paper_realtime
start_paper_status_web

cat <<EOF
启动完成（局域网测试模式）

Postgres 端口: ${POSTGRES_PORT}
Web 监听地址: ${PAPER_WEB_HOST}
Web 页面端口: ${PAPER_WEB_PORT}
Web 页面地址: http://局域网UbuntuIP:${PAPER_WEB_PORT}
端口配置文件: ${PORT_ENV}
日志目录: ${LOG_DIR}
启动模式: ${START_MODE}
EOF

if [[ "$START_MODE" == "foreground" ]]; then
  trap cleanup_foreground TERM INT
  wait -n "$PAPER_REALTIME_PID" "$PAPER_WEB_PID"
  exit_code="$?"
  cleanup_foreground
  exit "$exit_code"
fi
