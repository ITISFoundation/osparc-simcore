# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

from typing import Iterator
from uuid import uuid4

import pytest
from _pytest.monkeypatch import MonkeyPatch
from simcore_service_dynamic_sidecar.core.settings import DynamicSidecarSettings


@pytest.fixture
def mock_env(monkeypatch: MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("SC_BOOT_MODE", "production")
    monkeypatch.setenv("DYNAMIC_SIDECAR_compose_namespace", "test-space")
    monkeypatch.setenv("REGISTRY_auth", "false")
    monkeypatch.setenv("REGISTRY_user", "test")
    monkeypatch.setenv("REGISTRY_PW", "test")
    monkeypatch.setenv("REGISTRY_SSL", "false")
    monkeypatch.setenv("USER_ID", "1")
    monkeypatch.setenv("PROJECT_ID", f"{uuid4()}")
    monkeypatch.setenv("NODE_ID", f"{uuid4()}")

    yield None


def test_settings(mock_env: None) -> None:
    settings = DynamicSidecarSettings.create()
    assert settings

    assert settings.RABBIT_SETTINGS is not None
