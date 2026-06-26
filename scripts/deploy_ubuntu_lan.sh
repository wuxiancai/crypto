#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "此脚本面向 Ubuntu/Linux 局域网测试环境。当前系统: $(uname -s)" >&2
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

detect_lan_ip() {
  local detected_ip
  detected_ip="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
  if [[ -n "$detected_ip" ]]; then
    echo "$detected_ip"
    return
  fi
  echo "局域网UbuntuIP"
}

install_lan_systemd_service() {
  if ! command -v systemctl >/dev/null 2>&1; then
    echo "未检测到 systemd，回退为普通后台启动。"
    PAPER_WEB_HOST=0.0.0.0 bash "$ROOT_DIR/scripts/start_lan.sh"
    return
  fi

  local service_name="${SERVICE_NAME:-crypto-paper-lan}"
  local service_user="${SERVICE_USER:-${SUDO_USER:-$(id -un)}}"
  local service_group="${SERVICE_GROUP:-$(id -gn "$service_user")}"
  local runtime_dir="$ROOT_DIR/runtime"
  local unit_path="/etc/systemd/system/${service_name}.service"
  local supplementary_groups=""

  mkdir -p "$runtime_dir"
  if getent group docker >/dev/null 2>&1; then
    supplementary_groups="SupplementaryGroups=docker"
  fi

  local unit_file="$runtime_dir/${service_name}.service"
  cat > "$unit_file" <<EOF
[Unit]
Description=Crypto Paper Trading and Status Web LAN Test
Requires=docker.service
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${ROOT_DIR}
User=${service_user}
Group=${service_group}
${supplementary_groups}
Environment=PYTHONUNBUFFERED=1
Environment=START_MODE=foreground
Environment=PAPER_WEB_HOST=0.0.0.0
ExecStart=/bin/bash ${ROOT_DIR}/scripts/start_lan.sh
Restart=always
RestartSec=10
TimeoutStopSec=45
KillMode=control-group

[Install]
WantedBy=multi-user.target
EOF

  sudo install -m 0644 "$unit_file" "$unit_path"
  sudo systemctl daemon-reload
  sudo systemctl enable "${service_name}.service"
  sudo systemctl restart "${service_name}.service"

  cat <<EOF
systemd 局域网测试服务已安装并启动

服务名: ${service_name}.service
服务文件: ${unit_path}
查看状态: sudo systemctl status ${service_name}.service --no-pager
查看日志: sudo journalctl -u ${service_name}.service -f
停止服务: sudo systemctl stop ${service_name}.service
重启服务: sudo systemctl restart ${service_name}.service
EOF
}

print_lan_deploy_summary() {
  local port_env="$ROOT_DIR/.env.ports.generated"
  if [[ ! -f "$port_env" ]]; then
    echo "未找到端口配置文件：$port_env。请查看部署日志。" >&2
    return
  fi

  # shellcheck disable=SC1090
  source "$port_env"

  local lan_ip
  lan_ip="$(detect_lan_ip)"

  cat <<EOF

===========================================
Crypto Paper Trading 局域网测试部署完成
===========================================

Web 监听地址:
  0.0.0.0:${PAPER_WEB_PORT}

局域网访问地址:
  http://${lan_ip}:${PAPER_WEB_PORT}

如果无法访问，请检查：
  1. Ubuntu 防火墙是否放行：sudo ufw allow ${PAPER_WEB_PORT}/tcp
  2. Ubuntu 与访问设备是否在同一局域网
  3. 监听状态：sudo ss -lntp | grep ${PAPER_WEB_PORT}
  4. 本机连通：curl -I http://127.0.0.1:${PAPER_WEB_PORT}/
  5. 局域网连通：curl -I http://${lan_ip}:${PAPER_WEB_PORT}/

常用命令:
  查看服务: sudo systemctl status ${SERVICE_NAME:-crypto-paper-lan}.service --no-pager
  查看日志: sudo journalctl -u ${SERVICE_NAME:-crypto-paper-lan}.service -f
  应用日志: tail -f runtime/logs/paper-realtime.log
  停止服务: sudo systemctl stop ${SERVICE_NAME:-crypto-paper-lan}.service

说明:
  - 此脚本是局域网测试专用副本，不改原 deploy_ubuntu.sh / start.sh
  - Web 显式绑定 0.0.0.0，便于局域网通过 Ubuntu IP 访问
  - PostgreSQL 仍按 docker-compose.yml 绑定 127.0.0.1，不暴露数据库

EOF
}

install_python_packages
ensure_docker
ensure_env_file
install_lan_systemd_service
print_lan_deploy_summary
