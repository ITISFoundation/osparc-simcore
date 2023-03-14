# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import pytest
from _pytest.monkeypatch import MonkeyPatch
from osparc_gateway_server.backend.settings import AppSettings


@pytest.fixture
def minimal_config(monkeypatch: MonkeyPatch):
    monkeypatch.setenv("GATEWAY_WORKERS_NETWORK", "atestnetwork")
    monkeypatch.setenv("GATEWAY_SERVER_NAME", "atestserver")
    monkeypatch.setenv("COMPUTATIONAL_SIDECAR_IMAGE", "test/localpytest:latest")
    monkeypatch.setenv(
        "COMPUTATIONAL_SIDECAR_VOLUME_NAME", "sidecar_computational_volume_name"
    )


def test_app_settings(minimal_config):
    settings = AppSettings()
    assert settings
