# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from collections.abc import Iterable

import pytest
from fastapi import FastAPI
from settings_library.docker_registry import RegistrySettings
from simcore_service_dynamic_sidecar.core.registry import (
    DOCKER_CONFIG_JSON_PATH,
    _is_registry_reachable,
    _login_registries,
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
def cleanup_config_file() -> Iterable[None]:
    def _remove_config_json_file():
        if DOCKER_CONFIG_JSON_PATH.exists():
            DOCKER_CONFIG_JSON_PATH.unlink()
        assert DOCKER_CONFIG_JSON_PATH.exists() is False

    _remove_config_json_file()
    yield
    _remove_config_json_file()


@pytest.fixture
def unset_registry_envs(monkeypatch: pytest.MonkeyPatch) -> None:
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
    cleanup_config_file: None,
    monkeypatch: pytest.MonkeyPatch,
    docker_registry: str,
) -> None:
    monkeypatch.setenv(
        "DY_DEPLOYMENT_REGISTRY_SETTINGS",
        _get_registry_config(
            url=docker_registry, user="testuser", password="testpassword"  # noqa: S106
        ),
    )


async def test_is_registry_reachable(
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
    await _is_registry_reachable(registry_settings)


@pytest.fixture
def registries_env_mocker(
    unset_registry_envs: None,
    cleanup_config_file: None,
    monkeypatch: pytest.MonkeyPatch,
    envs: dict[str, str],
) -> None:
    for name, value in envs.items():
        monkeypatch.setenv(name, value)


@pytest.mark.parametrize(
    "envs, expected_config_file_content",
    [
        pytest.param(
            {
                "DY_DEPLOYMENT_REGISTRY_SETTINGS": _get_registry_config(),
            },
            '{"auths": {"localhost:1111": {"auth": "dXNlcjpwYXNzd29yZA=="}}}',
            id="only_internal_registry_no_dockerhub",
        ),
        pytest.param(
            {
                "DY_DEPLOYMENT_REGISTRY_SETTINGS": _get_registry_config(),
                "DY_DOCKER_HUB_REGISTRY_SETTINGS": "null",
            },
            '{"auths": {"localhost:1111": {"auth": "dXNlcjpwYXNzd29yZA=="}}}',
            id="only_internal_registry_dockerhub_set_null",
        ),
        pytest.param(
            {
                "DY_DEPLOYMENT_REGISTRY_SETTINGS": _get_registry_config(
                    url="dockerhuburl"
                ),
                "DY_DOCKER_HUB_REGISTRY_SETTINGS": _get_registry_config(),
            },
            '{"auths": {"dockerhuburl": {"auth": "dXNlcjpwYXNzd29yZA=="}, "localhost:1111": {"auth": "dXNlcjpwYXNzd29yZA=="}}}',
            id="internal_and_dockerhub_registry",
        ),
    ],
)
async def test__login_registries(
    registries_env_mocker: None,
    app: FastAPI,
    expected_config_file_content: str,
) -> None:
    await _login_registries(app.state.settings)
    assert DOCKER_CONFIG_JSON_PATH.read_text() == expected_config_file_content
