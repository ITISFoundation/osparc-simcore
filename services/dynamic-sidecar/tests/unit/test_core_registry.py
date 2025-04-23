# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from collections.abc import Iterable

import pytest
from fastapi import FastAPI
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.docker_registry import RegistrySettings
from simcore_service_dynamic_sidecar.core.registry import (
    DOCKER_CONFIG_JSON_PATH,
    _login_registry,
)


def _get_registry_config(
    *,
    url: str = "localhost:1111",
    auth: str = "true",
    user: str = "user",
    password: str = "password",  # noqa: S107
    ssl: str = "false",
) -> str:
    return json.dumps(
        {
            "REGISTRY_URL": url,
            "REGISTRY_AUTH": auth,
            "REGISTRY_USER": user,
            "REGISTRY_PW": password,
            "REGISTRY_SSL": ssl,
        }
    )


@pytest.fixture
def backup_docker_config_file() -> Iterable[None]:
    backup_path = (
        DOCKER_CONFIG_JSON_PATH.parent / f"{DOCKER_CONFIG_JSON_PATH.name}.backup"
    )

    if not backup_path.exists() and DOCKER_CONFIG_JSON_PATH.exists():
        backup_path.write_text(DOCKER_CONFIG_JSON_PATH.read_text())

    if DOCKER_CONFIG_JSON_PATH.exists():
        DOCKER_CONFIG_JSON_PATH.unlink()

    yield

    if backup_path.exists():
        DOCKER_CONFIG_JSON_PATH.write_text(backup_path.read_text())
        backup_path.unlink()


@pytest.fixture
def unset_registry_envs(
    mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> None:
    for env in (
        "REGISTRY_AUTH",
        "REGISTRY_PATH",
        "REGISTRY_URL",
        "REGISTRY_USER",
        "REGISTRY_PW",
        "REGISTRY_SSL",
    ):
        monkeypatch.delenv(env, raising=False)


@pytest.fixture
def mock_registry_settings_with_auth(
    unset_registry_envs: None,
    backup_docker_config_file: None,
    monkeypatch: pytest.MonkeyPatch,
    docker_registry: str,
) -> None:
    monkeypatch.setenv(
        "DY_DEPLOYMENT_REGISTRY_SETTINGS",
        _get_registry_config(
            url=docker_registry,
            user="testuser",
            password="testpassword",  # noqa: S106
        ),
    )


async def test__login_registry(
    mock_registry_settings_with_auth: None,
    app: FastAPI,
    docker_registry: str,
) -> None:
    registry_settings: RegistrySettings = (
        app.state.settings.DY_DEPLOYMENT_REGISTRY_SETTINGS
    )
    assert registry_settings.REGISTRY_URL == docker_registry  # noqa: SIM300
    assert registry_settings.REGISTRY_AUTH is True
    assert registry_settings.REGISTRY_USER == "testuser"
    assert registry_settings.REGISTRY_PW.get_secret_value() == "testpassword"
    assert registry_settings.REGISTRY_SSL is False

    await _login_registry(registry_settings)

    config_json = json.loads(DOCKER_CONFIG_JSON_PATH.read_text())
    assert len(config_json["auths"]) == 1
    assert registry_settings.REGISTRY_URL in config_json["auths"]
