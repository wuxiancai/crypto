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
    sudo apt-get install -y docker.io docker-compose-plugin
  fi
}

ensure_compose() {
  if docker compose version >/dev/null 2>&1; then
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    return
  fi

  if docker_ce_available; then
    sudo apt-get install -y docker-compose-plugin
  else
    sudo apt-get install -y docker-compose-plugin || sudo apt-get install -y docker-compose
  fi
}

ensure_docker() {
  install_docker_engine
  ensure_compose

  if command -v systemctl >/dev/null 2>&1 && ! systemctl is-active --quiet docker; then
    sudo systemctl enable --now docker
  fi
}

install_python_packages
ensure_docker

bash "$ROOT_DIR/scripts/start_ubuntu.sh"
