from pathlib import Path


def test_allocate_ports_skips_used_ports():
    from app.deploy.ports import allocate_ports

    allocated = allocate_ports(
        requested={"POSTGRES_PORT": 55432, "PAPER_WEB_PORT": 8765},
        is_port_available=lambda port: port not in {55432, 55433, 8765},
    )

    assert allocated == {"POSTGRES_PORT": 55434, "PAPER_WEB_PORT": 8766}


def test_write_env_file_contains_database_url_and_selected_ports(tmp_path, monkeypatch):
    from app.deploy.ports import write_ports_env

    path = tmp_path / ".env.ports.generated"

    monkeypatch.setenv("POSTGRES_USER", "crypto")
    monkeypatch.setenv("POSTGRES_PASSWORD", "s3cret-pass")
    monkeypatch.setenv("POSTGRES_DB", "crypto_quant")

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
    assert "POSTGRES_PASSWORD=s3cret-pass" in content
    assert (
        "DATABASE_URL=postgresql+psycopg://crypto:s3cret-pass@localhost:55434/crypto_quant"
        in content
    )
    assert "BINANCE_WEBSOCKET_BASE_URL=wss://fstream.binance.com/market" in content
    assert "PAPER_STATE_PATH=runtime/paper-state.json" in content


def test_write_env_file_generates_password_when_unset(tmp_path, monkeypatch):
    from app.deploy.ports import write_ports_env

    path = tmp_path / ".env.ports.generated"

    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)

    write_ports_env(path, {"POSTGRES_PORT": 55432, "PAPER_WEB_PORT": 8765})

    content = path.read_text(encoding="utf-8")
    password_line = next(
        line for line in content.splitlines() if line.startswith("POSTGRES_PASSWORD=")
    )
    generated = password_line.split("=", 1)[1]

    assert generated not in {"", "crypto"}
    assert len(generated) >= 16


def test_write_env_file_reuses_existing_password(tmp_path, monkeypatch):
    from app.deploy.ports import write_ports_env

    path = tmp_path / ".env.ports.generated"
    path.write_text("POSTGRES_PASSWORD=kept-stable\n", encoding="utf-8")

    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)

    write_ports_env(path, {"POSTGRES_PORT": 55432, "PAPER_WEB_PORT": 8765})

    assert "POSTGRES_PASSWORD=kept-stable" in path.read_text(encoding="utf-8")


def test_backfill_reuses_password_from_legacy_database_url(tmp_path, monkeypatch):
    from app.deploy.ports import backfill_credentials_env

    path = tmp_path / ".env.ports.generated"
    path.write_text(
        "POSTGRES_PORT=55433\n"
        "PAPER_WEB_PORT=8765\n"
        "DATABASE_URL=postgresql+psycopg://crypto:crypto@localhost:55433/crypto_quant\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)

    backfill_credentials_env(path)

    content = path.read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD=crypto" in content
    assert "DATABASE_URL=postgresql+psycopg://crypto:crypto@localhost:55433/crypto_quant" in content


def test_write_env_file_url_encodes_custom_password(tmp_path, monkeypatch):
    from app.deploy.ports import write_ports_env

    path = tmp_path / ".env.ports.generated"

    monkeypatch.setenv("POSTGRES_USER", "crypto")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss:word/with#chars")
    monkeypatch.setenv("POSTGRES_DB", "crypto_quant")

    write_ports_env(path, {"POSTGRES_PORT": 55432, "PAPER_WEB_PORT": 8765})

    content = path.read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD=p@ss:word/with#chars" in content
    assert "DATABASE_URL=postgresql+psycopg://crypto:p%40ss%3Aword%2Fwith%23chars@localhost:55432/crypto_quant" in content


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


def test_compose_limits_postgres_resources_for_small_ubuntu_host():
    content = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "mem_limit: 512m" in content
    assert "shared_buffers=128MB" in content
    assert "work_mem=4MB" in content
    assert "maintenance_work_mem=64MB" in content
    assert "max_connections=30" in content


def test_ubuntu_start_subscribes_weekly_daily_h4_intervals():
    content = Path("scripts/start.sh").read_text(encoding="utf-8")

    assert "--intervals 1w 1d 4h" in content
    assert "--enable-layered-strategy" not in content
