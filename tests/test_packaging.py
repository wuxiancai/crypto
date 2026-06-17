import tomllib
from pathlib import Path


def test_setuptools_only_packages_app_package():
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    find_config = config["tool"]["setuptools"]["packages"]["find"]

    assert find_config["include"] == ["app*"]
    assert "runtime*" in find_config["exclude"]
    assert "migrations*" in find_config["exclude"]
