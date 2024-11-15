# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any, Final

import pytest
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.dynamic_services_scheduler import SchedulerData
from simcore_service_director_v2.modules.dynamic_sidecar.docker_service_specs.sidecar import (
    _get_environment_variables,
    _get_storage_config,
    _StorageConfig,
)

# PLEASE keep alphabetical to simplify debugging
EXPECTED_DYNAMIC_SIDECAR_ENV_VAR_NAMES: Final[set[str]] = {
    "DY_DEPLOYMENT_REGISTRY_SETTINGS",
    "DY_DOCKER_HUB_REGISTRY_SETTINGS",
    "DY_SIDECAR_AWS_S3_CLI_SETTINGS",
    "DY_SIDECAR_CALLBACKS_MAPPING",
    "DY_SIDECAR_LOG_FORMAT_LOCAL_DEV_ENABLED",
    "DY_SIDECAR_NODE_ID",
    "DY_SIDECAR_PATH_INPUTS",
    "DY_SIDECAR_PATH_OUTPUTS",
    "DY_SIDECAR_PRODUCT_NAME",
    "DY_SIDECAR_PROJECT_ID",
    "DY_SIDECAR_RUN_ID",
    "DY_SIDECAR_SERVICE_KEY",
    "DY_SIDECAR_SERVICE_VERSION",
    "DY_SIDECAR_STATE_EXCLUDE",
    "DY_SIDECAR_STATE_PATHS",
    "DY_SIDECAR_SYSTEM_MONITOR_TELEMETRY_ENABLE",
    "DY_SIDECAR_USER_ID",
    "DY_SIDECAR_USER_PREFERENCES_PATH",
    "DY_SIDECAR_USER_SERVICES_HAVE_INTERNET_ACCESS",
    "DYNAMIC_SIDECAR_COMPOSE_NAMESPACE",
    "DYNAMIC_SIDECAR_LOG_LEVEL",
    "DYNAMIC_SIDECAR_TRACING",
    "NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS",
    "POSTGRES_DB",
    "POSTGRES_ENDPOINT",
    "POSTGRES_HOST",
    "POSTGRES_PASSWORD",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "R_CLONE_OPTION_BUFFER_SIZE",
    "R_CLONE_OPTION_RETRIES",
    "R_CLONE_OPTION_TRANSFERS",
    "R_CLONE_PROVIDER",
    "RABBIT_HOST",
    "RABBIT_PASSWORD",
    "RABBIT_PORT",
    "RABBIT_SECURE",
    "RABBIT_USER",
    "S3_ACCESS_KEY",
    "S3_BUCKET_NAME",
    "S3_ENDPOINT",
    "S3_REGION",
    "S3_SECRET_KEY",
    "SC_BOOT_MODE",
    "SIMCORE_HOST_NAME",
    "SSL_CERT_FILE",
    "STORAGE_HOST",
    "STORAGE_PASSWORD",
    "STORAGE_PORT",
    "STORAGE_SECURE",
    "STORAGE_USERNAME",
}


def test_dynamic_sidecar_env_vars(
    scheduler_data_from_http_request: SchedulerData,
    project_env_devel_environment: dict[str, Any],
):
    app_settings = AppSettings.create_from_envs()

    dynamic_sidecar_env_vars = _get_environment_variables(
        "compose_namespace",
        scheduler_data_from_http_request,
        app_settings,
        allow_internet_access=False,
        metrics_collection_allowed=True,
        telemetry_enabled=True,
    )
    print("dynamic_sidecar_env_vars:", dynamic_sidecar_env_vars)

    assert set(dynamic_sidecar_env_vars) == EXPECTED_DYNAMIC_SIDECAR_ENV_VAR_NAMES


@pytest.mark.parametrize(
    "env_vars, expected_storage_config",
    [
        pytest.param(
            {},
            _StorageConfig("storage", "8080", "null", "null", "0"),
            id="no_env_vars",
        ),
        pytest.param(
            {
                "STORAGE_HOST": "just-storage",
                "STORAGE_PORT": "123",
            },
            _StorageConfig("just-storage", "123", "null", "null", "0"),
            id="host-and-port",
        ),
        pytest.param(
            {
                "STORAGE_HOST": "storage-with-auth",
                "STORAGE_PORT": "42",
                "STORAGE_PASSWORD": "pass",
                "STORAGE_USERNAME": "user",
            },
            _StorageConfig("storage-with-auth", "42", "user", "pass", "0"),
            id="host-port-pass-user",
        ),
        pytest.param(
            {
                "STORAGE_HOST": "storage-with-auth",
                "STORAGE_PORT": "42",
                "STORAGE_PASSWORD": "pass",
                "STORAGE_USERNAME": "user",
                "STORAGE_SECURE": "1",
            },
            _StorageConfig("storage-with-auth", "42", "user", "pass", "1"),
            id="host-port-pass-user-secure-true",
        ),
        pytest.param(
            {
                "STORAGE_HOST": "normal-storage",
                "STORAGE_PORT": "8081",
                "DIRECTOR_V2_NODE_PORTS_STORAGE_AUTH": (
                    "{"
                    '"STORAGE_USERNAME": "overwrite-user", '
                    '"STORAGE_PASSWORD": "overwrite-passwd", '
                    '"STORAGE_HOST": "overwrite-host", '
                    '"STORAGE_PORT": "44", '
                    '"STORAGE_SECURE": "1"'
                    "}"
                ),
            },
            _StorageConfig(
                "overwrite-host", "44", "overwrite-user", "overwrite-passwd", "1"
            ),
            id="host-port-and-node-ports-config",
        ),
        pytest.param(
            {
                "DIRECTOR_V2_NODE_PORTS_STORAGE_AUTH": (
                    "{"
                    '"STORAGE_USERNAME": "overwrite-user", '
                    '"STORAGE_PASSWORD": "overwrite-passwd", '
                    '"STORAGE_HOST": "overwrite-host", '
                    '"STORAGE_PORT": "44"'
                    "}"
                ),
            },
            _StorageConfig(
                "overwrite-host", "44", "overwrite-user", "overwrite-passwd", "0"
            ),
            id="only-node-ports-config",
        ),
    ],
)
def test__get_storage_config(
    project_env_devel_environment: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    env_vars: dict[str, str],
    expected_storage_config: _StorageConfig,
):
    setenvs_from_dict(monkeypatch, env_vars)
    app_settings = AppSettings.create_from_envs()

    assert _get_storage_config(app_settings) == expected_storage_config
