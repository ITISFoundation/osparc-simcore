from typing import Dict

from _pytest.monkeypatch import MonkeyPatch
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.schemas.dynamic_services.scheduler import (
    SchedulerData,
)
from simcore_service_director_v2.modules.dynamic_sidecar.docker_service_specs.sidecar import (
    _get_dy_sidecar_env_vars,
)

MOCKED_PASSWORD = "pwd"

MOCKED_BASE_REGISTRY_ENV_VARS: Dict[str, str] = {
    "REGISTRY_AUTH": "False",
    "REGISTRY_USER": "usr",
    "REGISTRY_PW": MOCKED_PASSWORD,
    "REGISTRY_SSL": "False",
    "DYNAMIC_SIDECAR_IMAGE": "itisfoundation/dynamic-sidecar:MOCK",
    "POSTGRES_HOST": "test",
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": "test",
    "POSTGRES_DB": "test",
}

EXPECTED_DYNAMIC_SIDECAR_ENV_VAR_NAMES = {
    "DY_SIDECAR_PATH_INPUTS",
    "DY_SIDECAR_PATH_OUTPUTS",
    "DY_SIDECAR_STATE_PATHS",
    "DY_SIDECAR_USER_ID",
    "DY_SIDECAR_PROJECT_ID",
    "DY_SIDECAR_NODE_ID",
    "POSTGRES_HOST",
    "POSTGRES_ENDPOINT",
    "POSTGRES_PASSWORD",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_DB",
    "STORAGE_ENDPOINT",
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

    app_settings = AppSettings.create_from_envs()

    dynamic_sidecar_env_vars = _get_dy_sidecar_env_vars(
        scheduler_data_from_http_request, app_settings
    )
    print("dynamic_sidecar_env_vars:", dynamic_sidecar_env_vars)

    assert len(dynamic_sidecar_env_vars) == len(EXPECTED_DYNAMIC_SIDECAR_ENV_VAR_NAMES)
    assert set(dynamic_sidecar_env_vars) == EXPECTED_DYNAMIC_SIDECAR_ENV_VAR_NAMES
