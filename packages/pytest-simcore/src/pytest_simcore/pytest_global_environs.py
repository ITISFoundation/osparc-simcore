import pytest


@pytest.fixture(autouse=True)
def sqlalchemy_2_0_warnings(monkeypatch):
    monkeypatch.setenv("SQLALCHEMY_WARN_20", "1")


@pytest.fixture(autouse=True)
def patch_log_format_local_dev_enabled(monkeypatch):
    monkeypatch.setenv("LOG_FORMAT_LOCAL_DEV_ENABLED", "1")
