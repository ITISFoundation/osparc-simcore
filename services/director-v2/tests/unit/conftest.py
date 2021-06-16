import pytest


@pytest.fixture(autouse=True)
def disable_dynamic_sidecar_monitor_in_unit_tests(monkeypatch) -> None:
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SERVICES_enabled", "false")
    monkeypatch.setenv("REGISTRY_auth", "false")
    monkeypatch.setenv("REGISTRY_user", "test")
    monkeypatch.setenv("REGISTRY_PW", "test")
    monkeypatch.setenv("REGISTRY_ssl", "false")
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", "test_network_name")
    monkeypatch.setenv("TRAEFIK_SIMCORE_ZONE", "test_traefik_zone")
    monkeypatch.setenv("SWARM_STACK_NAME", "test_swarm_name")
