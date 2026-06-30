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
KLINE_SYNC_STRICT_ON_START="${KLINE_SYNC_STRICT_ON_START:-0}"
BINANCE_CONNECTIVITY_CHECK_ON_START="${BINANCE_CONNECTIVITY_CHECK_ON_START:-1}"
BINANCE_CONNECT_TIMEOUT="${BINANCE_CONNECT_TIMEOUT:-10}"
BINANCE_MAX_TIME="${BINANCE_MAX_TIME:-25}"
RUNTIME_DIR="$ROOT_DIR/runtime"
LOG_DIR="$RUNTIME_DIR/logs"
PAPER_REALTIME_PID=""
PAPER_WEB_PID=""
ENABLE_BATCH_BACKTEST="${ENABLE_BATCH_BACKTEST:-0}"

for arg in "$@"; do
  case "$arg" in
    --ENABLE_BACKTEST)
      ENABLE_BATCH_BACKTEST=1
      ;;
    -h|--help)
      cat <<EOF
用法: bash scripts/start.sh [--ENABLE_BACKTEST]

选项:
  --ENABLE_BACKTEST   启用 Web 批量回测功能。默认禁用，避免公网访问触发重计算或清空回测记录。
EOF
      exit 0
      ;;
    *)
      echo "未知参数: $arg" >&2
      echo "用法: bash scripts/start.sh [--ENABLE_BACKTEST]" >&2
      exit 2
      ;;
  esac
done

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
if [[ -f "$ROOT_DIR/.env" ]]; then
  source "$ROOT_DIR/.env"
fi
source "$PORT_ENV"
set +a

BINANCE_BASE_URL="${BINANCE_BASE_URL:-https://fapi.binance.com}"
BINANCE_WEBSOCKET_BASE_URL="${BINANCE_WEBSOCKET_BASE_URL:-wss://fstream.binance.com/market}"

if [[ "$ENABLE_BATCH_BACKTEST" == "1" ]]; then
  export PAPER_ENABLE_BATCH_BACKTEST=1
fi

STATUS_WEB_ARGS=()
BATCH_BACKTEST_STATUS="默认禁用"
if [[ "${PAPER_ENABLE_BATCH_BACKTEST:-0}" == "1" ]]; then
  STATUS_WEB_ARGS+=(--enable-batch-backtest)
  BATCH_BACKTEST_STATUS="已启用"
fi

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
  echo "可临时执行：sudo bash scripts/start.sh" >&2
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

DATABASE_URL="$DATABASE_URL" "$VENV_PYTHON" -m alembic upgrade head

check_binance_connectivity() {
  if [[ "$BINANCE_CONNECTIVITY_CHECK_ON_START" != "1" ]]; then
    echo "已跳过 Binance 启动前连通性检查。"
    return
  fi

  if ! command -v curl >/dev/null 2>&1; then
    echo "缺少 curl，无法执行 Binance 启动前连通性检查。请先安装 curl，或设置 BINANCE_CONNECTIVITY_CHECK_ON_START=0 跳过。" >&2
    exit 1
  fi

  local ping_url="${BINANCE_BASE_URL%/}/fapi/v1/ping"
  local kline_url="${BINANCE_BASE_URL%/}/fapi/v1/klines?symbol=BTCUSDT&interval=1d&limit=1"

  echo "启动前检查 Binance Futures REST 连通性..."
  if ! curl -fsS --connect-timeout "$BINANCE_CONNECT_TIMEOUT" --max-time "$BINANCE_MAX_TIME" "$ping_url" >/dev/null; then
    cat >&2 <<EOF
Binance REST 连通性检查失败：无法访问 ${ping_url}
已停止启动，避免在无法连接 Binance 的情况下继续启动 WebSocket/Paper Trading。
请在目标服务器上检查:
  1. curl -fsS --connect-timeout ${BINANCE_CONNECT_TIMEOUT} --max-time ${BINANCE_MAX_TIME} ${ping_url}
  2. DNS、代理、防火墙、服务器所在网络/地区是否限制访问 Binance Futures。
如确认只想离线打开状态页，可临时设置 BINANCE_CONNECTIVITY_CHECK_ON_START=0。
EOF
    exit 1
  fi

  if ! curl -fsS --connect-timeout "$BINANCE_CONNECT_TIMEOUT" --max-time "$BINANCE_MAX_TIME" "$kline_url" >/dev/null; then
    cat >&2 <<EOF
Binance 日线 K 线连通性检查失败：无法访问 ${kline_url}
已停止启动，避免在 BTCUSDT 1d 历史数据不可用时继续启动 WebSocket/Paper Trading。
请在目标服务器上检查:
  1. curl -fsS --connect-timeout ${BINANCE_CONNECT_TIMEOUT} --max-time ${BINANCE_MAX_TIME} '${kline_url}'
  2. runtime/logs/paper-realtime.log 是否有 Binance REST/WebSocket 相关错误。
  3. DNS、代理、防火墙、服务器所在网络/地区是否限制访问 Binance Futures。
如确认只想离线打开状态页，可临时设置 BINANCE_CONNECTIVITY_CHECK_ON_START=0。
EOF
    exit 1
  fi
}

sync_required_klines() {
  echo "检查并补齐策略所需 K 线数据..."
  if DATABASE_URL="$DATABASE_URL" "$VENV_PYTHON" scripts/sync_klines.py \
    --symbols BTCUSDT ETHUSDT \
    --intervals 1w 1d 4h \
    --limit "$KLINE_SYNC_LIMIT" \
    --write; then
    return
  fi

  if [[ "$KLINE_SYNC_STRICT_ON_START" == "1" ]]; then
    echo "K 线同步失败，严格模式下停止启动。请检查 Binance REST 连通性。" >&2
    exit 1
  fi

  cat >&2 <<EOF
Binance REST 连接超时或失败，已跳过启动前 K 线同步并继续启动。
这通常表示当前机器到 Binance REST 不通、超时，或所在网络/地区受限。
后续若页面没有新的策略评估，请优先检查:
  1. runtime/logs/paper-realtime.log
  2. curl -fsS https://fapi.binance.com/fapi/v1/ping
  3. curl -fsS 'https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=1d&limit=1'
如需恢复旧的硬失败行为，可设置 KLINE_SYNC_STRICT_ON_START=1。
EOF
}

check_binance_connectivity
sync_required_klines

start_paper_realtime() {
  if [[ "$START_MODE" == "foreground" ]]; then
    "$VENV_PYTHON" scripts/run_paper_realtime.py \
      --symbols BTCUSDT ETHUSDT \
      --intervals 1w 1d 4h \
      --websocket-base-url "$BINANCE_WEBSOCKET_BASE_URL" \
      --state-path "$PAPER_STATE_PATH" \
      >> "$LOG_DIR/paper-realtime.log" 2>&1 &
  else
    nohup "$VENV_PYTHON" scripts/run_paper_realtime.py \
      --symbols BTCUSDT ETHUSDT \
      --intervals 1w 1d 4h \
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
      --host 0.0.0.0 \
      --port "$PAPER_WEB_PORT" \
      --state-path "$PAPER_STATE_PATH" \
      --error-log-path "$LOG_DIR/paper-realtime.log" \
      "${STATUS_WEB_ARGS[@]}" \
      >> "$LOG_DIR/paper-status-web.log" 2>&1 &
  else
    nohup "$VENV_PYTHON" scripts/run_paper_status_web.py \
      --host 0.0.0.0 \
      --port "$PAPER_WEB_PORT" \
      --state-path "$PAPER_STATE_PATH" \
      --error-log-path "$LOG_DIR/paper-realtime.log" \
      "${STATUS_WEB_ARGS[@]}" \
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

print_child_exit_logs() {
  local exit_code="$1"

  echo "Paper 子进程退出，服务将停止并交给 systemd 处理。退出码: ${exit_code}" >&2

  if [[ -n "$PAPER_REALTIME_PID" ]] && ! kill -0 "$PAPER_REALTIME_PID" >/dev/null 2>&1; then
    echo "Paper 实时交易进程退出。最近日志如下：" >&2
    tail -n 120 "$LOG_DIR/paper-realtime.log" >&2 || true
  fi

  if [[ -n "$PAPER_WEB_PID" ]] && ! kill -0 "$PAPER_WEB_PID" >/dev/null 2>&1; then
    echo "Paper Web 状态页进程退出。最近日志如下：" >&2
    tail -n 120 "$LOG_DIR/paper-status-web.log" >&2 || true
  fi
}

start_paper_realtime
start_paper_status_web

cat <<EOF
启动完成

Postgres 端口: ${POSTGRES_PORT}
Web 页面端口: ${PAPER_WEB_PORT}
Web 页面地址: http://服务器IP:${PAPER_WEB_PORT}
端口配置文件: ${PORT_ENV}
日志目录: ${LOG_DIR}
启动模式: ${START_MODE}
Binance 启动前连通性检查: ${BINANCE_CONNECTIVITY_CHECK_ON_START}
批量回测 Web 功能: ${BATCH_BACKTEST_STATUS}
EOF

if [[ "$START_MODE" == "foreground" ]]; then
  trap cleanup_foreground TERM INT
  set +e
  wait -n "$PAPER_REALTIME_PID" "$PAPER_WEB_PID"
  exit_code="$?"
  set -e
  print_child_exit_logs "$exit_code"
  cleanup_foreground
  exit "$exit_code"
fi
