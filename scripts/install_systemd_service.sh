#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="${SERVICE_NAME:-crypto-paper}"
SERVICE_USER="${SERVICE_USER:-${SUDO_USER:-$(id -un)}}"
SERVICE_GROUP="${SERVICE_GROUP:-$(id -gn "$SERVICE_USER")}"
RUNTIME_DIR="$ROOT_DIR/runtime"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "systemd service installation only supports Linux." >&2
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl not found. Please use scripts/start.sh manually on this host." >&2
  exit 1
fi

mkdir -p "$RUNTIME_DIR"

SUPPLEMENTARY_GROUPS=""
if getent group docker >/dev/null 2>&1; then
  SUPPLEMENTARY_GROUPS="SupplementaryGroups=docker"
fi

unit_file="$RUNTIME_DIR/${SERVICE_NAME}.service"
cat > "$unit_file" <<EOF
[Unit]
Description=Crypto Paper Trading and Status Web
Requires=docker.service
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${ROOT_DIR}
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
${SUPPLEMENTARY_GROUPS}
Environment=PYTHONUNBUFFERED=1
Environment=START_MODE=foreground
ExecStart=/bin/bash ${ROOT_DIR}/scripts/start.sh
Restart=always
RestartSec=10
TimeoutStopSec=45
KillMode=control-group

[Install]
WantedBy=multi-user.target
EOF

sudo install -m 0644 "$unit_file" "$UNIT_PATH"
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}.service"
sudo systemctl restart "${SERVICE_NAME}.service"

cat <<EOF
systemd 服务已安装并启动

服务名: ${SERVICE_NAME}.service
服务文件: ${UNIT_PATH}
查看状态: sudo systemctl status ${SERVICE_NAME}.service --no-pager
查看日志: sudo journalctl -u ${SERVICE_NAME}.service -f
停止服务: sudo systemctl stop ${SERVICE_NAME}.service
重启服务: sudo systemctl restart ${SERVICE_NAME}.service
EOF
