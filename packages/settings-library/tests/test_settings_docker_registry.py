# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from copy import deepcopy
from typing import Dict

import pytest
from _pytest.monkeypatch import MonkeyPatch
from settings_library.docker_registry import RegistrySettings

MOCKED_BASE_REGISTRY_ENV_VARS: Dict[str, str] = {
    "REGISTRY_AUTH": "False",
    "REGISTRY_USER": "usr",
    "REGISTRY_PW": "pwd",
    "REGISTRY_SSL": "False",
}


def _add_parameter_to_default_env(key: str, value: str) -> Dict[str, str]:
    registry_env = deepcopy(MOCKED_BASE_REGISTRY_ENV_VARS)
    registry_env[key] = value
    return registry_env


def _mock_env_vars(monkeypatch: MonkeyPatch, env_vars: Dict[str, str]) -> None:
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize(
    "env_key, env_var",
    [
        ("REGISTRY_PATH", "some_dev_path"),
        ("REGISTRY_URL", "some_prod_url"),
    ],
)
def test_model_ok(env_key: str, env_var: str, monkeypatch: MonkeyPatch) -> None:
    registry_env_vars = _add_parameter_to_default_env(env_key, env_var)
    _mock_env_vars(monkeypatch, registry_env_vars)

    registry_settings = RegistrySettings()
    assert registry_settings
    assert registry_settings.resolved_registry_url == env_var
