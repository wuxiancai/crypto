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
  停止服务: bash scripts/stop.sh

EOF
}

install_python_packages
ensure_docker
ensure_env_file

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
