# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Any, Dict, Set

import pytest
from _pytest.monkeypatch import MonkeyPatch
from models_library.basic_types import LogLevel
from simcore_service_director_v2.core.settings import (
    AppSettings,
    BootModeEnum,
    DynamicSidecarProxySettings,
    DynamicSidecarSettings,
    RCloneSettings,
    S3Provider,
)


def _get_backend_type_options() -> Set[str]:
    return {x for x in dir(S3Provider) if not x.startswith("_")}


def test_supported_backends_did_not_change() -> None:
    _EXPECTED = {"AWS", "CEPH", "MINIO"}
    assert _EXPECTED == _get_backend_type_options(), (
        "Backend configuration change, please code support for "
        "it in volumes_resolver -> _get_s3_volume_driver_config. "
        "When done, adjust above list."
    )


@pytest.mark.parametrize(
    "endpoint, is_secure",
    [
        ("localhost", False),
        ("s3_aws", True),
        ("https://ceph.home", True),
        ("http://local.dev", False),
    ],
)
def test_expected_s3_endpoint(
    endpoint: str, is_secure: bool, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("R_CLONE_S3_PROVIDER", "MINIO")
    monkeypatch.setenv("S3_ENDPOINT", endpoint)
    monkeypatch.setenv("S3_SECURE", "true" if is_secure else "false")

    r_clone_settings = RCloneSettings()

    scheme = "https" if is_secure else "http"
    assert r_clone_settings.endpoint.startswith(f"{scheme}://")
    assert r_clone_settings.endpoint.endswith(endpoint)


def test_enforce_r_clone_requirement(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("R_CLONE_S3_PROVIDER", "MINIO")
    monkeypatch.setenv("R_CLONE_POLL_INTERVAL_SECONDS", "11")
    with pytest.raises(ValueError):
        RCloneSettings()


def test_settings_with_project_env_devel(project_env_devel_environment: Dict[str, Any]):
    # loads from environ
    settings = AppSettings.create_from_envs()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.SC_BOOT_MODE == BootModeEnum.DEBUG
    assert settings.LOG_LEVEL == LogLevel.DEBUG

    assert settings.POSTGRES.dsn == "postgresql://test:test@localhost:5432/test"


def test_settings_with_env_devel(mock_env_devel_environment: Dict[str, str]):
    settings = AppSettings.create_from_envs()
    print("captured settings: \n", settings.json(indent=2))
    assert settings


@pytest.mark.parametrize(
    "image",
    [
        "local/dynamic-sidecar:development",
        "local/dynamic-sidecar:production",
        "itisfoundation/dynamic-sidecar:merge-github-testbuild-latest",
        "itisfoundation/dynamic-sidecar:1.0.0",
        "local/dynamic-sidecar:0.0.1",
        "dynamic-sidecar:production",
        "/dynamic-sidecar:latest",
        "/local/dynamic-sidecar:latest",
    ],
)
def test_dynamic_sidecar_settings(
    image: str, project_env_devel_environment: Dict[str, Any]
) -> None:
    required_kwards = dict(
        DYNAMIC_SIDECAR_IMAGE=image,
        SIMCORE_SERVICES_NETWORK_NAME="test",
        TRAEFIK_SIMCORE_ZONE="",
        SWARM_STACK_NAME="",
        DYNAMIC_SIDECAR_PROXY_SETTINGS=DynamicSidecarProxySettings(),
    )
    settings = DynamicSidecarSettings(**required_kwards)

    assert settings.DYNAMIC_SIDECAR_IMAGE == image.lstrip("/")
