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


def test_start_script_reuses_existing_generated_ports():
    content = Path("scripts/start.sh").read_text(encoding="utf-8")

    assert 'REGENERATE_PORTS="${REGENERATE_PORTS:-0}"' in content
    assert '[[ "$REGENERATE_PORTS" == "1" || ! -f "$PORT_ENV" ]]' in content
    assert "Using existing port config" in content


def test_start_script_removes_compose_orphans():
    content = Path("scripts/start.sh").read_text(encoding="utf-8")

    assert "--remove-orphans postgres" in content


def test_start_script_passes_realtime_error_log_to_status_page():
    content = Path("scripts/start.sh").read_text(encoding="utf-8")

    assert "--error-log-path" in content
    assert "$LOG_DIR/paper-realtime.log" in content


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


def test_deploy_script_installs_systemd_service():
    content = Path("scripts/deploy_ubuntu.sh").read_text(encoding="utf-8")

    assert "install_systemd_service" in content
    assert "scripts/install_systemd_service.sh" in content
    assert "systemctl" in content


def test_systemd_install_script_uses_start_script_in_foreground_mode():
    content = Path("scripts/install_systemd_service.sh").read_text(encoding="utf-8")

    assert "START_MODE=foreground" in content
    assert "ExecStart=/bin/bash ${ROOT_DIR}/scripts/start.sh" in content
    assert "Restart=always" in content
    assert "systemctl enable" in content
    assert "systemctl restart" in content
