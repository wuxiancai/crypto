#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "此脚本面向 Ubuntu/Linux 服务器。当前系统: $(uname -s)" >&2
  exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "未找到 apt-get。请先安装 python3、python3-venv、docker 和 docker compose。" >&2
  exit 1
fi

sudo apt-get update

install_python_packages() {
  sudo apt-get install -y python3 python3-venv python3-pip
}

docker_ce_available() {
  apt-cache policy docker-ce 2>/dev/null | grep -q "Candidate: " \
    && ! apt-cache policy docker-ce 2>/dev/null | grep -q "Candidate: (none)"
}

install_docker_engine() {
  if command -v docker >/dev/null 2>&1; then
    echo "Docker already installed: $(docker --version)"
    return
  fi

  if docker_ce_available; then
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  else
    sudo apt-get install -y docker.io
  fi
}

install_compose_package() {
  sudo apt-get install -y docker-compose-plugin \
    || sudo apt-get install -y docker-compose-v2 \
    || sudo apt-get install -y docker-compose
}

ensure_compose() {
  if docker compose version >/dev/null 2>&1; then
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    return
  fi

  install_compose_package

  if ! docker compose version >/dev/null 2>&1 && ! command -v docker-compose >/dev/null 2>&1; then
    echo "Docker Compose 安装失败。请检查 apt 源，或手动安装 docker compose / docker-compose 后重试。" >&2
    exit 1
  fi
}

ensure_docker() {
  install_docker_engine
  ensure_compose

  if command -v systemctl >/dev/null 2>&1 && ! systemctl is-active --quiet docker; then
    sudo systemctl enable --now docker
  fi
}

ensure_env_file() {
  if [[ -f "$ROOT_DIR/.env" ]]; then
    echo ".env already exists; keep existing application config."
    return
  fi
  if [[ -f "$ROOT_DIR/.env.example" ]]; then
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    echo "已创建 .env：cp .env.example .env"
  fi
}

sudo_docker() {
  if docker info >/dev/null 2>&1; then
    docker "$@"
    return
  fi
  sudo docker "$@"
}

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

  echo "无法访问 Docker Compose。请确认 Docker 已启动，并且当前用户在 docker 组，或当前用户可以执行 sudo docker。" >&2
  exit 1
}

existing_database_volumes() {
  sudo_docker volume ls --format '{{.Name}}' 2>/dev/null | grep -E '(^|_)crypto_quant_postgres_data$' || true
}

previous_deploy_markers() {
  local markers=()
  if [[ -f "$ROOT_DIR/.env.ports.generated" ]]; then
    markers+=(".env.ports.generated")
  fi
  if [[ -f "$ROOT_DIR/runtime/paper-state.json" ]]; then
    markers+=("runtime/paper-state.json")
  fi
  while IFS= read -r volume_name; do
    [[ -n "$volume_name" ]] && markers+=("docker volume: ${volume_name}")
  done < <(existing_database_volumes)

  if [[ "${#markers[@]}" -eq 0 ]]; then
    return
  fi

  printf '%s\n' "${markers[@]}"
}

confirm_database_mode() {
  local markers
  markers="$(previous_deploy_markers)"
  if [[ -z "$markers" ]]; then
    return
  fi

  local mode="${DEPLOY_DATABASE_MODE:-}"
  if [[ -z "$mode" && -t 0 ]]; then
    cat <<EOF

检测到当前服务器可能已经部署过本项目：
${markers}

请选择数据库处理方式：
  1) 保留数据库并继续部署（推荐）
  2) 删除数据库和本地 Paper 状态后重新部署
EOF
    read -r -p "请输入 1 或 2 [默认 1]: " mode
    case "$mode" in
      2|reset|RESET) mode="reset" ;;
      *) mode="keep" ;;
    esac
  fi

  if [[ -z "$mode" ]]; then
    mode="keep"
  fi

  case "$mode" in
    keep|KEEP|1)
      echo "保留已有数据库和 Paper 状态继续部署。"
      ;;
    reset|RESET|2)
      reset_previous_database
      ;;
    *)
      echo "DEPLOY_DATABASE_MODE 只能是 keep 或 reset，当前值: $mode" >&2
      exit 1
      ;;
  esac
}

reset_previous_database() {
  echo "准备删除旧数据库和本地 Paper 状态..."
  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files crypto-paper.service >/dev/null 2>&1; then
    sudo systemctl stop crypto-paper.service >/dev/null 2>&1 || true
  fi

  if [[ -f "$ROOT_DIR/.env.ports.generated" ]]; then
    compose --env-file "$ROOT_DIR/.env.ports.generated" down -v --remove-orphans >/dev/null 2>&1 || true
  else
    compose down -v --remove-orphans >/dev/null 2>&1 || true
  fi

  while IFS= read -r volume_name; do
    [[ -n "$volume_name" ]] && sudo_docker volume rm "$volume_name" >/dev/null 2>&1 || true
  done < <(existing_database_volumes)

  rm -f "$ROOT_DIR/runtime/paper-state.json"
  echo "旧数据库和本地 Paper 状态已删除，将重新部署。"
}

detect_server_ip() {
  if [[ -n "${PUBLIC_HOST:-}" ]]; then
    echo "$PUBLIC_HOST"
    return
  fi
  local detected_ip
  detected_ip="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
  if [[ -n "$detected_ip" ]]; then
    echo "$detected_ip"
    return
  fi
  echo "服务器公网IP"
}

print_deploy_summary() {
  local port_env="$ROOT_DIR/.env.ports.generated"
  if [[ ! -f "$port_env" ]]; then
    echo "未找到端口配置文件：$port_env。请查看部署日志。" >&2
    return
  fi

  # shellcheck disable=SC1090
  source "$port_env"

  local server_ip
  server_ip="$(detect_server_ip)"

  cat <<EOF

===========================================
Crypto Paper Trading 部署完成
===========================================

Web 页面地址:
  http://${server_ip}:${PAPER_WEB_PORT}

如果上面显示的是内网 IP，请使用云服务器公网 IP 打开:
  http://<云服务器公网IP>:${PAPER_WEB_PORT}

端口信息:
  Web 页面端口: ${PAPER_WEB_PORT}
  PostgreSQL 端口: ${POSTGRES_PORT}
  端口配置文件: ${port_env}

下一步必须确认:
  1. 云厂商安全组放行 TCP ${PAPER_WEB_PORT}
  2. 如果启用了 ufw，执行: sudo ufw allow ${PAPER_WEB_PORT}/tcp
  3. 浏览器打开: http://<云服务器公网IP>:${PAPER_WEB_PORT}

.env 配置说明:
  - 已自动创建 .env（如果之前不存在）
  - 第一版只跑 Paper，不需要配置 Binance API Key
  - 默认使用 Binance 主网行情: BINANCE_BASE_URL=https://fapi.binance.com
  - 如果服务器访问 Binance 主网受限，可在 .env 中改为可访问的 futures endpoint
  - 实际运行端口和数据库连接以 .env.ports.generated 为准，通常不需要手动修改 DATABASE_URL

常用命令:
  查看服务: sudo systemctl status crypto-paper.service --no-pager
  查看日志: sudo journalctl -u crypto-paper.service -f
  应用日志: tail -f runtime/logs/paper-realtime.log
  本机监听: sudo ss -lntp | grep ${PAPER_WEB_PORT}
  本机连通: curl -I http://127.0.0.1:${PAPER_WEB_PORT}/
  停止服务: bash scripts/stop.sh

EOF
}

install_python_packages
ensure_docker
ensure_env_file
confirm_database_mode

install_systemd_service() {
  if command -v systemctl >/dev/null 2>&1; then
    bash "$ROOT_DIR/scripts/install_systemd_service.sh"
    return
  fi

  echo "未检测到 systemd，回退为普通后台启动。"
  bash "$ROOT_DIR/scripts/start.sh"
}

install_systemd_service
print_deploy_summary
