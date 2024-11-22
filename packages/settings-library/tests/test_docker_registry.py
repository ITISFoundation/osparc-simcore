# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from copy import deepcopy

import pytest
from settings_library.docker_registry import RegistrySettings

MOCKED_BASE_REGISTRY_ENV_VARS: dict[str, str] = {
    "REGISTRY_AUTH": "False",
    "REGISTRY_USER": "usr",
    "REGISTRY_PW": "pwd",
    "REGISTRY_SSL": "False",
    "REGISTRY_URL": "pytest.registry.com",
}


def _add_parameter_to_env(env: dict[str, str], key: str, value: str) -> dict[str, str]:
    registry_env = deepcopy(env)
    registry_env[key] = value
    return registry_env


def _mock_env_vars(monkeypatch: pytest.MonkeyPatch, env_vars: dict[str, str]) -> None:
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize(
    "env_key, env_var",
    [
        ("REGISTRY_PATH", "some_dev_path"),
        ("REGISTRY_URL", "some_prod_url"),
    ],
)
def test_model_ok(env_key: str, env_var: str, monkeypatch: pytest.MonkeyPatch) -> None:
    registry_env_vars = _add_parameter_to_env(
        MOCKED_BASE_REGISTRY_ENV_VARS, env_key, env_var
    )
    _mock_env_vars(monkeypatch, registry_env_vars)

    registry_settings = RegistrySettings()
    assert registry_settings
    assert registry_settings.resolved_registry_url == env_var


def test_registry_path_none_string(monkeypatch: pytest.MonkeyPatch) -> None:
    registry_env_vars = _add_parameter_to_env(
        MOCKED_BASE_REGISTRY_ENV_VARS, "REGISTRY_PATH", "None"
    )
    registry_env_vars = _add_parameter_to_env(
        registry_env_vars, "REGISTRY_URL", "some_prod_url"
    )
    _mock_env_vars(monkeypatch, registry_env_vars)

    registry_settings = RegistrySettings()
    assert registry_settings
    assert registry_settings.resolved_registry_url == registry_env_vars["REGISTRY_URL"]
