# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import uuid
from pathlib import Path

import pytest
from pytest import MonkeyPatch
from simcore_service_dynamic_sidecar.core.settings import (
    DynamicSidecarSettings,
    get_settings,
)


@pytest.fixture
def mocked_non_request_settings(
    tmp_path: Path, monkeypatch: MonkeyPatch, project_slug_dir: Path
) -> None:

    inputs_dir = tmp_path / "inputs"
    outputs_dir = tmp_path / "outputs"

    monkeypatch.setenv("SC_BOOT_MODE", "production")
    monkeypatch.setenv("DYNAMIC_SIDECAR_COMPOSE_NAMESPACE", "test-space")
    monkeypatch.setenv("REGISTRY_AUTH", "false")
    monkeypatch.setenv("REGISTRY_USER", "test")
    monkeypatch.setenv("REGISTRY_PW", "test")
    monkeypatch.setenv("REGISTRY_SSL", "false")
    monkeypatch.setenv("DY_SIDECAR_PATH_INPUTS", f"{inputs_dir}")
    monkeypatch.setenv("DY_SIDECAR_PATH_OUTPUTS", f"{outputs_dir}")
    monkeypatch.setenv("DY_SIDECAR_USER_ID", "1")
    monkeypatch.setenv("DY_SIDECAR_PROJECT_ID", f"{uuid.uuid4()}")
    monkeypatch.setenv("DY_SIDECAR_NODE_ID", f"{uuid.uuid4()}")

    monkeypatch.setenv("S3_ENDPOINT", "endpoint")
    monkeypatch.setenv("S3_ACCESS_KEY", "access_key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret_key")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket_name")
    monkeypatch.setenv("S3_SECURE", "false")
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")


def test_non_request_dynamic_sidecar_settings(
    mocked_non_request_settings: None,
) -> None:
    assert DynamicSidecarSettings.create_from_envs()


def test_cached_settings_is_same_object(mocked_non_request_settings: None) -> None:
    assert id(get_settings()) == id(get_settings())


def test_settings_with_envdevel_file(mock_environment_with_envdevel):
    assert DynamicSidecarSettings.create_from_envs()
