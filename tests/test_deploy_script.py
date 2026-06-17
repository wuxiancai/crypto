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
    content = Path("scripts/start_ubuntu.sh").read_text(encoding="utf-8")

    assert 'REGENERATE_PORTS="${REGENERATE_PORTS:-0}"' in content
    assert '[[ "$REGENERATE_PORTS" == "1" || ! -f "$PORT_ENV" ]]' in content
    assert "Using existing port config" in content


def test_start_script_removes_compose_orphans():
    content = Path("scripts/start_ubuntu.sh").read_text(encoding="utf-8")

    assert "--remove-orphans postgres" in content
