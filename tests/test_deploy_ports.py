from pathlib import Path


def test_allocate_ports_skips_used_ports():
    from app.deploy.ports import allocate_ports

    allocated = allocate_ports(
        requested={"POSTGRES_PORT": 55432, "PAPER_WEB_PORT": 8765},
        is_port_available=lambda port: port not in {55432, 55433, 8765},
    )

    assert allocated == {"POSTGRES_PORT": 55434, "PAPER_WEB_PORT": 8766}


def test_write_env_file_contains_database_url_and_selected_ports(tmp_path):
    from app.deploy.ports import write_ports_env

    path = tmp_path / ".env.ports.generated"

    write_ports_env(
        path,
        {
            "POSTGRES_PORT": 55434,
            "PAPER_WEB_PORT": 8766,
        },
    )

    content = path.read_text(encoding="utf-8")

    assert "POSTGRES_PORT=55434" in content
    assert "PAPER_WEB_PORT=8766" in content
    assert "DATABASE_URL=postgresql+psycopg://crypto:crypto@localhost:55434/crypto_quant" in content
    assert "BINANCE_WEBSOCKET_BASE_URL=wss://fstream.binance.com/market" in content
    assert "PAPER_STATE_PATH=runtime/paper-state.json" in content


def test_generate_ports_env_writes_shifted_ports(tmp_path):
    from app.deploy.ports import generate_ports_env

    path = tmp_path / ".env.ports.generated"

    allocated = generate_ports_env(
        path,
        is_port_available=lambda port: port not in {55432, 8765, 8766},
    )

    assert allocated["POSTGRES_PORT"] == 55433
    assert allocated["PAPER_WEB_PORT"] == 8767
    assert path.exists()


def test_docker_published_ports_are_treated_as_unavailable():
    from app.deploy.ports import docker_published_ports

    ports = docker_published_ports(
        command_runner=lambda _cmd: (
            "0.0.0.0:55432->5432/tcp, [::]:55432->5432/tcp\n"
            "127.0.0.1:8765->8765/tcp\n"
        )
    )

    assert ports == {55432, 8765}


def test_compose_does_not_pin_postgres_container_name():
    content = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "container_name:" not in content
