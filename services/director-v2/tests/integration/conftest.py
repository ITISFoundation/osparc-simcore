import pytest


@pytest.fixture(autouse=True)
def mock_dynamic_sidecar_settings(monkeypatch) -> None:
    monkeypatch.setenv(
        "DYNAMIC_SIDECAR_IMAGE", "local/dynamic-sidecar:TEST_MOCKED_TAG_NOT_PRESENT"
    )
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", "test_services_network_name")
    monkeypatch.setenv("TRAEFIK_SIMCORE_ZONE", "test_mocked_simcore_zone")
    monkeypatch.setenv("SWARM_STACK_NAME", "test_mocked_stack_name")
