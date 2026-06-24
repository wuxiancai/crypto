#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SERVICE_NAME="${SERVICE_NAME:-crypto-paper}"
PORT_ENV="$ROOT_DIR/.env.ports.generated"
RUNTIME_DIR="$ROOT_DIR/runtime"
STOP_POSTGRES="${STOP_POSTGRES:-1}"
STOP_SYSTEMD="${STOP_SYSTEMD:-1}"

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

  echo "未找到可用的 docker compose，跳过 PostgreSQL 容器停止。" >&2
  return 1
}

stop_systemd_service() {
  if [[ "$STOP_SYSTEMD" != "1" ]]; then
    return
  fi
  if ! command -v systemctl >/dev/null 2>&1; then
    return
  fi
  if ! systemctl list-unit-files "${SERVICE_NAME}.service" >/dev/null 2>&1; then
    return
  fi
  if ! systemctl is-active --quiet "${SERVICE_NAME}.service"; then
    return
  fi

  echo "停止 systemd 服务: ${SERVICE_NAME}.service"
  if sudo systemctl stop "${SERVICE_NAME}.service" >/dev/null 2>&1; then
    return
  fi

  echo "无法停止 systemd 服务，请手动检查: sudo systemctl status ${SERVICE_NAME}.service --no-pager" >&2
}

stop_pid_file() {
  local label="$1"
  local pid_file="$2"

  if [[ ! -f "$pid_file" ]]; then
    return
  fi

  local pid
  pid="$(tr -d '[:space:]' < "$pid_file" || true)"
  if [[ -z "$pid" ]]; then
    rm -f "$pid_file"
    return
  fi

  if kill -0 "$pid" >/dev/null 2>&1; then
    echo "停止 ${label}: ${pid}"
    kill "$pid" >/dev/null 2>&1 || true
    wait_for_pid_exit "$pid" || kill -9 "$pid" >/dev/null 2>&1 || true
  fi

  rm -f "$pid_file"
}

wait_for_pid_exit() {
  local pid="$1"
  for _ in $(seq 1 10); do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

stop_process_by_pattern() {
  local label="$1"
  local pattern="$2"
  local pids

  pids="$(pgrep -f "$pattern" || true)"
  if [[ -z "$pids" ]]; then
    return
  fi

  echo "停止残留 ${label}: ${pids//$'\n'/ }"
  kill $pids >/dev/null 2>&1 || true

  for _ in $(seq 1 10); do
    if ! pgrep -f "$pattern" >/dev/null 2>&1; then
      return
    fi
    sleep 1
  done

  pids="$(pgrep -f "$pattern" || true)"
  if [[ -n "$pids" ]]; then
    echo "强制停止残留 ${label}: ${pids//$'\n'/ }"
    kill -9 $pids >/dev/null 2>&1 || true
  fi
}

stop_postgres() {
  if [[ "$STOP_POSTGRES" != "1" ]]; then
    return
  fi

  echo "停止 PostgreSQL 容器..."
  if [[ -f "$PORT_ENV" ]]; then
    compose --env-file "$PORT_ENV" stop postgres >/dev/null 2>&1 || true
  else
    compose stop postgres >/dev/null 2>&1 || true
  fi
}

stop_systemd_service

stop_pid_file "Paper 实时交易进程" "$RUNTIME_DIR/paper-realtime.pid"
stop_pid_file "Paper Web 状态页进程" "$RUNTIME_DIR/paper-status-web.pid"

stop_process_by_pattern "Paper 实时交易进程" "scripts/run_paper_realtime.py"
stop_process_by_pattern "Paper Web 状态页进程" "scripts/run_paper_status_web.py"

stop_postgres

echo "项目进程停止完成。"
