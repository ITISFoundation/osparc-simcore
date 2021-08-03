from typing import Dict

from _pytest.monkeypatch import MonkeyPatch
from settings_library.docker_registry import RegistrySettings
from simcore_service_director_v2.utils.registry import get_dynamic_sidecar_env_vars

MOCKED_PASSWORD = "pwd"

MOCKED_BASE_REGISTRY_ENV_VARS: Dict[str, str] = {
    "REGISTRY_AUTH": "False",
    "REGISTRY_USER": "usr",
    "REGISTRY_PW": MOCKED_PASSWORD,
    "REGISTRY_SSL": "False",
}

EXPECTED_DYNAMIC_SIDECAR_ENV_VAR_NAMES = {
    "REGISTRY_AUTH",
    "REGISTRY_PATH",
    "REGISTRY_URL",
    "REGISTRY_USER",
    "REGISTRY_PW",
    "REGISTRY_SSL",
}


def test_dynamic_sidecar_env_vars(monkeypatch: MonkeyPatch) -> None:
    for key, value in MOCKED_BASE_REGISTRY_ENV_VARS.items():
        monkeypatch.setenv(key, value)

    registry_settings = RegistrySettings()

    dynamic_sidecar_env_vars = get_dynamic_sidecar_env_vars(registry_settings)
    print("dynamic_sidecar_env_vars:", dynamic_sidecar_env_vars)

    assert len(dynamic_sidecar_env_vars) == len(EXPECTED_DYNAMIC_SIDECAR_ENV_VAR_NAMES)
    assert set(dynamic_sidecar_env_vars) == EXPECTED_DYNAMIC_SIDECAR_ENV_VAR_NAMES

    assert dynamic_sidecar_env_vars["REGISTRY_AUTH"] == str(
        registry_settings.REGISTRY_AUTH
    )
    assert dynamic_sidecar_env_vars["REGISTRY_PATH"] == str(
        registry_settings.REGISTRY_PATH
    )
    assert dynamic_sidecar_env_vars["REGISTRY_URL"] == str(
        registry_settings.REGISTRY_URL
    )
    assert dynamic_sidecar_env_vars["REGISTRY_USER"] == str(
        registry_settings.REGISTRY_USER
    )
    assert dynamic_sidecar_env_vars["REGISTRY_PW"] == str(
        registry_settings.REGISTRY_PW.get_secret_value()
    )
    assert dynamic_sidecar_env_vars["REGISTRY_SSL"] == str(
        registry_settings.REGISTRY_SSL
    )

    assert str(registry_settings.REGISTRY_PW) == "**********"
    assert registry_settings.REGISTRY_PW.get_secret_value() == MOCKED_PASSWORD
