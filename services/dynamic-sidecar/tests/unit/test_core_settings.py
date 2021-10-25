# pylint: disable=unused-argument

import os
from typing import Iterator
from unittest import mock

import pytest
from simcore_service_dynamic_sidecar.core.settings import DynamicSidecarSettings


@pytest.fixture
def mock_env() -> Iterator[None]:
    with mock.patch.dict(
        os.environ,
        {
            "SC_BOOT_MODE": "production",
            "DYNAMIC_SIDECAR_compose_namespace": "test-space",
            "REGISTRY_auth": "false",
            "REGISTRY_user": "test",
            "REGISTRY_PW": "test",
            "REGISTRY_SSL": "false",
        },
    ):
        yield None


def test_settings(mock_env: None) -> None:
    settings = DynamicSidecarSettings.create()
    assert settings

    assert settings.RABBIT_SETTINGS is not None
