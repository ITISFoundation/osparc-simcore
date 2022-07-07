# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from models_library.basic_types import LogLevel
from pydantic import ValidationError
from pytest import FixtureRequest
from settings_library.r_clone import S3Provider
from simcore_service_director_v2.core.settings import (
    AppSettings,
    BootModeEnum,
    DynamicSidecarSettings,
    RCloneSettings,
)


def _get_backend_type_options() -> set[str]:
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
        ("s3_aws", False),
        ("https://ceph.home", True),
        ("http://local.dev", False),
    ],
)
def test_expected_s3_endpoint(
    endpoint: str, is_secure: bool, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
    monkeypatch.setenv("S3_ENDPOINT", endpoint)
    monkeypatch.setenv("S3_SECURE", "true" if is_secure else "false")
    monkeypatch.setenv("S3_ACCESS_KEY", "access_key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret_key")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket_name")

    r_clone_settings = RCloneSettings()

    scheme = "https" if is_secure else "http"
    assert r_clone_settings.R_CLONE_S3.S3_ENDPOINT.startswith(f"{scheme}://")
    assert r_clone_settings.R_CLONE_S3.S3_ENDPOINT.endswith(endpoint)


def test_enforce_r_clone_requirement(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
    monkeypatch.setenv("R_CLONE_POLL_INTERVAL_SECONDS", "11")
    with pytest.raises(ValueError):
        RCloneSettings()


def test_settings_with_project_env_devel(project_env_devel_environment: dict[str, Any]):
    # loads from environ
    settings = AppSettings.create_from_envs()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.SC_BOOT_MODE == BootModeEnum.DEBUG
    assert settings.LOG_LEVEL == LogLevel.DEBUG

    assert settings.POSTGRES.dsn == "postgresql://test:test@localhost:5432/test"


def test_settings_with_env_devel(mock_env_devel_environment: dict[str, str]):
    settings = AppSettings.create_from_envs()
    print("captured settings: \n", settings.json(indent=2))
    assert settings


@pytest.fixture(
    params=[
        "local/dynamic-sidecar:development",
        "local/dynamic-sidecar:production",
        "itisfoundation/dynamic-sidecar:merge-github-testbuild-latest",
        "itisfoundation/dynamic-sidecar:1.0.0",
        "itisfoundation/dynamic-sidecar:staging-github-staging_diolkos1-2022-06-15--15-04.75ddf7e3fb86944ef95fcf77e4075464848121f1",
        "itisfoundation/dynamic-sidecar:hotfix-github-2022-06-24--12-34.162bfe899d6b62d808e70a07da280fd390bc4434",
        "itisfoundation/dynamic-sidecar:hotfix-v1-28-1-github-testbuild-latest",
        "itisfoundation/dynamic-sidecar:staging-github-latest",
        "itisfoundation/dynamic-sidecar:release-github-v1.28.0-2022-05-30--14-52.62c4c48b1846ecaa8280773f48a2f14bf0f3047b",
        "itisfoundation/dynamic-sidecar:master-github-2022-06-24--14-35.38add6817bc8cafabc14ec7dacd9b249daa3a11e",
        "local/dynamic-sidecar:sadasd",
        "itisfoundation/dynamic-sidecar:sadasd",
        "10.10.10.10.no.ip:8080/dynamic-sidecar:10.0.1",
        "10.10.10.10.no-ip:8080/dynamic-sidecar:sadasd",
        "10.10.10.10:8080/dynamic-sidecar:10.0.1",
        "10.10.10.10:8080/dynamic-sidecar:sadasd",
        "local/dynamic-sidecar:0.0.1",
        "dynamic-sidecar:production",
        "/dynamic-sidecar:latest",
        "/local/dynamic-sidecar:latest",
    ],
)
def testing_environ_expected_success(
    request: FixtureRequest,
    project_env_devel_environment,
    monkeypatch: MonkeyPatch,
) -> str:
    container_path: str = request.param
    monkeypatch.setenv("DYNAMIC_SIDECAR_IMAGE", container_path)
    return container_path


def test_dynamic_sidecar_settings(testing_environ_expected_success: str) -> None:
    settings = DynamicSidecarSettings()
    assert settings.DYNAMIC_SIDECAR_IMAGE == testing_environ_expected_success.lstrip(
        "/"
    )


@pytest.fixture(
    params=[
        "10.10.10.10.no/ip:8080/dynamic-sidecar:sadasd",
        "10.10.10.10.no$ip:8080/dynamic-sidecar:the_tag",
    ],
)
def testing_environ_expected_failure(
    request: FixtureRequest,
    project_env_devel_environment,
    monkeypatch: MonkeyPatch,
):
    container_path: str = request.param
    monkeypatch.setenv("DYNAMIC_SIDECAR_IMAGE", container_path)


def test_expected_failure_dynamic_sidecar_settings(
    testing_environ_expected_failure,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        DynamicSidecarSettings()


@pytest.mark.parametrize(
    "custom_constraints, expected",
    (
        ("[]", []),
        ('["one==yes"]', ["one==yes"]),
        ('["two!=no"]', ["two!=no"]),
        ('["one==yes", "two!=no"]', ["one==yes", "two!=no"]),
        ('["     strips.white.spaces   ==  ok "]', ["strips.white.spaces   ==  ok"]),
    ),
)
def test_services_custom_constraints(
    custom_constraints: str,
    expected: list[str],
    project_env_devel_environment,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIRECTOR_V2_SERVICES_CUSTOM_CONSTRAINTS", custom_constraints)
    settings = AppSettings()
    assert type(settings.DIRECTOR_V2_SERVICES_CUSTOM_CONSTRAINTS) == list
    assert settings.DIRECTOR_V2_SERVICES_CUSTOM_CONSTRAINTS == expected


def test_services_custom_constraints_default_empty_list(
    project_env_devel_environment,
) -> None:
    settings = AppSettings()
    assert settings.DIRECTOR_V2_SERVICES_CUSTOM_CONSTRAINTS == []
