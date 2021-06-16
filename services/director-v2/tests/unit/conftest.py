import pytest
from fastapi import FastAPI


@pytest.fixture(autouse=True)
def disable_dynamic_sidecar_monitor_in_unit_tests(
    minimal_app: FastAPI, monkeypatch
) -> None:
    minimal_app.app.state.dynamic_services.enabled = False
    monkeypatch.setenv("REGISTRY_auth", "false")
    monkeypatch.setenv("REGISTRY_user", "test")
    monkeypatch.setenv("REGISTRY_PW", "test")
    monkeypatch.setenv("REGISTRY_ssl", "false")
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", "test_network_name")
    monkeypatch.setenv("TRAEFIK_SIMCORE_ZONE", "test_traefik_zone")
    monkeypatch.setenv("SWARM_STACK_NAME", "test_swarm_name")
