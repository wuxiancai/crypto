#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "此脚本面向 Ubuntu/Linux 服务器。当前系统: $(uname -s)" >&2
  exit 1
fi

if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv python3-pip docker.io docker-compose-plugin
else
  echo "未找到 apt-get。请先安装 python3、python3-venv、docker 和 docker compose。" >&2
  exit 1
fi

if ! systemctl is-active --quiet docker; then
  sudo systemctl enable --now docker
fi

bash "$ROOT_DIR/scripts/start_ubuntu.sh"
