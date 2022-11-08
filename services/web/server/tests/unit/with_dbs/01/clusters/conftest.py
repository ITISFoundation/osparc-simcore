import pytest
from pytest import MonkeyPatch


@pytest.fixture
def enable_dev_features(monkeypatch: MonkeyPatch):
    monkeypatch.setenv("WEBSERVER_DEV_FEATURES_ENABLED", "1")
