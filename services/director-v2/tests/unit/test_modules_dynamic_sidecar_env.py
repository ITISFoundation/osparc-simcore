import json
from typing import Dict
from uuid import UUID

from _pytest.monkeypatch import MonkeyPatch
from settings_library.docker_registry import RegistrySettings
from settings_library.rabbit import RabbitSettings
from simcore_service_director_v2.models.schemas.dynamic_services.scheduler import (
    SchedulerData,
)
from simcore_service_director_v2.modules.dynamic_sidecar.env import (
    get_dynamic_sidecar_env_vars,
)

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
    "RABBIT_HOST",
    "RABBIT_PORT",
    "RABBIT_USER",
    "RABBIT_PASSWORD",
    "RABBIT_CHANNELS",
    "USER_ID",
    "PROJECT_ID",
    "NODE_ID",
}


def test_dynamic_sidecar_env_vars(
    monkeypatch: MonkeyPatch, scheduler_data_from_http_request: SchedulerData
) -> None:
    for key, value in MOCKED_BASE_REGISTRY_ENV_VARS.items():
        monkeypatch.setenv(key, value)

    registry_settings = RegistrySettings()
    rabbit_settings = RabbitSettings()

    dynamic_sidecar_env_vars = get_dynamic_sidecar_env_vars(
        scheduler_data_from_http_request, registry_settings, rabbit_settings
    )
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

    assert dynamic_sidecar_env_vars["RABBIT_HOST"] == str(rabbit_settings.RABBIT_HOST)
    assert dynamic_sidecar_env_vars["RABBIT_PORT"] == str(rabbit_settings.RABBIT_PORT)
    assert dynamic_sidecar_env_vars["RABBIT_USER"] == str(rabbit_settings.RABBIT_USER)
    assert str(rabbit_settings.RABBIT_PASSWORD) == "**********"
    assert dynamic_sidecar_env_vars["RABBIT_PASSWORD"] == str(
        rabbit_settings.RABBIT_PASSWORD.get_secret_value()
    )
    assert json.dumps(
        dynamic_sidecar_env_vars["RABBIT_CHANNELS"] == rabbit_settings.RABBIT_CHANNELS
    )

    assert int(dynamic_sidecar_env_vars["USER_ID"]) >= 0
    assert UUID(dynamic_sidecar_env_vars["PROJECT_ID"])
    assert UUID(dynamic_sidecar_env_vars["NODE_ID"])
