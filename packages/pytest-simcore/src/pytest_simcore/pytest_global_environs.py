import pytest


@pytest.fixture(autouse=True)
def sqlalchemy_2_0_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    # Major Migration Guide: https://docs.sqlalchemy.org/en/20/changelog/migration_20.html
    monkeypatch.setenv("SQLALCHEMY_WARN_20", "1")
    monkeypatch.setenv("LOG_FORMAT_LOCAL_DEV_ENABLED", "True")
