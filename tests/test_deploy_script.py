from pathlib import Path


def test_deploy_script_does_not_install_docker_io_unconditionally():
    content = Path("scripts/deploy_ubuntu.sh").read_text(encoding="utf-8")

    assert "install_python_packages" in content
    assert "ensure_docker" in content
    assert "sudo apt-get install -y python3 python3-venv python3-pip docker.io" not in content
    assert "command -v docker" in content


def test_deploy_script_prefers_existing_docker_and_supports_docker_ce():
    content = Path("scripts/deploy_ubuntu.sh").read_text(encoding="utf-8")

    assert "Docker already installed" in content
    assert "docker-ce" in content
    assert "docker.io" in content
    assert "docker compose version" in content


def test_deploy_script_does_not_require_compose_plugin_when_installing_docker_io():
    content = Path("scripts/deploy_ubuntu.sh").read_text(encoding="utf-8")

    assert "sudo apt-get install -y docker.io docker-compose-plugin" not in content
    assert "sudo apt-get install -y docker.io" in content
    assert "install_compose_package" in content
    assert "sudo apt-get install -y docker-compose-plugin" in content
    assert "sudo apt-get install -y docker-compose-v2" in content
    assert "sudo apt-get install -y docker-compose" in content


def test_start_script_reuses_existing_generated_ports():
    content = Path("scripts/start.sh").read_text(encoding="utf-8")

    assert 'REGENERATE_PORTS="${REGENERATE_PORTS:-0}"' in content
    assert '[[ "$REGENERATE_PORTS" == "1" || ! -f "$PORT_ENV" ]]' in content
    assert "Using existing port config" in content
    assert 'if [[ -f "$ROOT_DIR/.env" ]]; then' in content
    assert 'source "$ROOT_DIR/.env"' in content
    assert 'BINANCE_BASE_URL="${BINANCE_BASE_URL:-https://fapi.binance.com}"' in content
    assert 'BINANCE_WEBSOCKET_BASE_URL="${BINANCE_WEBSOCKET_BASE_URL:-wss://fstream.binance.com/market}"' in content


def test_start_script_removes_compose_orphans():
    content = Path("scripts/start.sh").read_text(encoding="utf-8")

    assert "--remove-orphans postgres" in content


def test_start_script_checks_docker_daemon_permission_before_compose_selection():
    content = Path("scripts/start.sh").read_text(encoding="utf-8")

    assert "docker info >/dev/null 2>&1 && docker compose version" in content
    assert "sudo docker info >/dev/null 2>&1 && sudo docker compose version" in content
    assert "无法访问 Docker" in content
    assert "sudo usermod -aG docker ${docker_user}" in content


def test_start_script_passes_realtime_error_log_to_status_page():
    content = Path("scripts/start.sh").read_text(encoding="utf-8")

    assert "--error-log-path" in content
    assert "$LOG_DIR/paper-realtime.log" in content


def test_start_script_enable_backtest_flag_enables_batch_backtest():
    content = Path("scripts/start.sh").read_text(encoding="utf-8")

    assert "--ENABLE_BACKTEST" in content
    assert "ENABLE_BATCH_BACKTEST=1" in content
    assert "PAPER_ENABLE_BATCH_BACKTEST=1" in content
    assert 'STATUS_WEB_ARGS+=(--enable-batch-backtest)' in content
    assert 'BATCH_BACKTEST_STATUS="已启用"' in content
    assert "批量回测 Web 功能: ${BATCH_BACKTEST_STATUS}" in content


def test_start_script_stops_existing_project_before_starting():
    content = Path("scripts/start.sh").read_text(encoding="utf-8")

    assert "stop_existing_project" in content
    assert "stop_process_by_pattern" in content
    assert "scripts/run_paper_realtime.py" in content
    assert "scripts/run_paper_status_web.py" in content
    assert "compose --env-file \"$PORT_ENV\" stop postgres" in content
    assert content.index("stop_existing_project") < content.index("up -d --remove-orphans postgres")


def test_start_script_supports_systemd_foreground_mode():
    content = Path("scripts/start.sh").read_text(encoding="utf-8")

    assert 'START_MODE="${START_MODE:-background}"' in content
    assert '[[ "$START_MODE" == "foreground" ]]' in content
    assert "wait -n" in content
    assert "trap cleanup_foreground TERM INT" in content


def test_start_script_prints_child_logs_before_systemd_restart():
    content = Path("scripts/start.sh").read_text(encoding="utf-8")

    assert "print_child_exit_logs" in content
    assert "Paper 实时交易进程退出。最近日志如下：" in content
    assert 'tail -n 120 "$LOG_DIR/paper-realtime.log"' in content
    assert "Paper Web 状态页进程退出。最近日志如下：" in content
    assert 'tail -n 120 "$LOG_DIR/paper-status-web.log"' in content
    assert content.index("wait -n") < content.index("print_child_exit_logs \"$exit_code\"")
    assert content.index("print_child_exit_logs \"$exit_code\"") < content.rindex("cleanup_foreground")


def test_start_script_syncs_required_klines_before_realtime_runner():
    content = Path("scripts/start.sh").read_text(encoding="utf-8")

    assert 'KLINE_SYNC_LIMIT="${KLINE_SYNC_LIMIT:-800}"' in content
    assert "scripts/sync_klines.py" in content
    assert "--intervals 1w 1d 4h" in content
    assert "--write" in content
    assert content.index("alembic upgrade head") < content.index("scripts/sync_klines.py")
    assert content.index("scripts/sync_klines.py") < content.index("start_paper_realtime")


def test_start_script_allows_best_effort_kline_sync_on_start():
    content = Path("scripts/start.sh").read_text(encoding="utf-8")

    assert 'KLINE_SYNC_STRICT_ON_START="${KLINE_SYNC_STRICT_ON_START:-0}"' in content
    assert 'if [[ "$KLINE_SYNC_STRICT_ON_START" == "1" ]]; then' in content
    assert "Binance REST 连接超时或失败，已跳过启动前 K 线同步并继续启动。" in content
    assert "curl -fsS https://fapi.binance.com/fapi/v1/ping" in content
    assert "curl -fsS 'https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=1d&limit=1'" in content
    assert "curl -I https://fapi.binance.com/fapi/v1/ping" not in content


def test_start_script_checks_binance_connectivity_before_realtime_runner():
    content = Path("scripts/start.sh").read_text(encoding="utf-8")

    assert 'BINANCE_CONNECTIVITY_CHECK_ON_START="${BINANCE_CONNECTIVITY_CHECK_ON_START:-1}"' in content
    assert 'BINANCE_CONNECT_TIMEOUT="${BINANCE_CONNECT_TIMEOUT:-10}"' in content
    assert 'BINANCE_MAX_TIME="${BINANCE_MAX_TIME:-25}"' in content
    assert "check_binance_connectivity" in content
    assert "启动前检查 Binance Futures REST 连通性" in content
    assert "${BINANCE_BASE_URL%/}/fapi/v1/ping" in content
    assert "BINANCE_BASE_URL=\"${BINANCE_BASE_URL:-https://fapi.binance.com}\"" in content
    assert "symbol=BTCUSDT&interval=1d&limit=1" in content
    assert "已停止启动，避免在无法连接 Binance 的情况下继续启动 WebSocket/Paper Trading。" in content
    assert "已停止启动，避免在 BTCUSDT 1d 历史数据不可用时继续启动 WebSocket/Paper Trading。" in content
    assert "BINANCE_CONNECTIVITY_CHECK_ON_START=0" in content
    assert content.index("check_binance_connectivity") < content.index("sync_required_klines")
    assert content.index("check_binance_connectivity") < content.index("start_paper_realtime")


def test_deploy_script_installs_systemd_service():
    content = Path("scripts/deploy_ubuntu.sh").read_text(encoding="utf-8")

    assert "install_systemd_service" in content
    assert "scripts/install_systemd_service.sh" in content
    assert "systemctl" in content


def test_deploy_script_prints_access_url_and_next_steps():
    content = Path("scripts/deploy_ubuntu.sh").read_text(encoding="utf-8")

    assert "ensure_env_file" in content
    assert "cp .env.example .env" in content
    assert "print_deploy_summary" in content
    assert "detect_server_ip" in content
    assert "hostname -I" in content
    assert "Web 页面地址" in content
    assert "http://${server_ip}:${PAPER_WEB_PORT}" in content
    assert "云服务器公网IP" in content
    assert "sudo ufw allow ${PAPER_WEB_PORT}/tcp" in content
    assert "BINANCE_BASE_URL=https://fapi.binance.com" in content
    assert "第一版只跑 Paper，不需要配置 Binance API Key" in content
    assert "实际运行端口和数据库连接以 .env.ports.generated 为准" in content
    assert "sudo ss -lntp | grep ${PAPER_WEB_PORT}" in content
    assert "curl -I http://127.0.0.1:${PAPER_WEB_PORT}/" in content


def test_deploy_script_prompts_before_resetting_existing_database():
    content = Path("scripts/deploy_ubuntu.sh").read_text(encoding="utf-8")

    assert "confirm_database_mode" in content
    assert "previous_deploy_markers" in content
    assert "DEPLOY_DATABASE_MODE" in content
    assert "reset_previous_database" in content
    assert "docker volume ls --format '{{.Name}}'" in content
    assert "crypto_quant_postgres_data" in content
    assert "保留数据库并继续部署" in content
    assert "删除数据库和本地 Paper 状态后重新部署" in content
    assert "compose --env-file \"$ROOT_DIR/.env.ports.generated\" down -v --remove-orphans" in content
    assert "runtime/paper-state.json" in content
    assert content.index("ensure_env_file") < content.index("confirm_database_mode")
    assert content.index("confirm_database_mode") < content.index("install_systemd_service")


def test_systemd_install_script_uses_start_script_in_foreground_mode():
    content = Path("scripts/install_systemd_service.sh").read_text(encoding="utf-8")

    assert "START_MODE=foreground" in content
    assert "KLINE_SYNC_STRICT_ON_START=0" in content
    assert "ExecStart=/bin/bash ${ROOT_DIR}/scripts/start.sh" in content
    assert "Restart=on-failure" in content
    assert "StartLimitIntervalSec=300" in content
    assert "StartLimitBurst=3" in content
    assert "systemctl enable" in content
    assert "systemctl restart" in content


def test_stop_script_stops_all_project_processes():
    content = Path("scripts/stop.sh").read_text(encoding="utf-8")

    assert 'SERVICE_NAME="${SERVICE_NAME:-crypto-paper}"' in content
    assert "sudo systemctl stop" in content
    assert "runtime/paper-realtime.pid" in content or "paper-realtime.pid" in content
    assert "runtime/paper-status-web.pid" in content or "paper-status-web.pid" in content
    assert "scripts/run_paper_realtime.py" in content
    assert "scripts/run_paper_status_web.py" in content
    assert "pgrep -f" in content
    assert "compose --env-file \"$PORT_ENV\" stop postgres" in content
    assert 'STOP_POSTGRES="${STOP_POSTGRES:-1}"' in content


def test_stop_script_checks_docker_daemon_permission_before_compose_selection():
    content = Path("scripts/stop.sh").read_text(encoding="utf-8")

    assert "docker info >/dev/null 2>&1 && docker compose version" in content
    assert "sudo docker info >/dev/null 2>&1 && sudo docker compose version" in content
    assert "无法访问 Docker，跳过 PostgreSQL 容器停止" in content


def test_status_web_disables_batch_backtest_by_default():
    content = Path("scripts/run_paper_status_web.py").read_text(encoding="utf-8")

    assert "PAPER_ENABLE_BATCH_BACKTEST" in content
    assert "enable_batch_backtest: bool = False" in content
    assert "默认禁用" in content
