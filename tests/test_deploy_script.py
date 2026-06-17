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
