import pytest


@pytest.fixture(autouse=True)
def disable_dynamic_sidecar_monitor_in_unit_tests(monkeypatch):
    monkeypatch.setenv("DYNAMIC_SIDECAR_DISABLE_MONITOR", "true")
