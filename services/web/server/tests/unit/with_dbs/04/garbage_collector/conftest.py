import pytest


@pytest.fixture(scope="session")
def fast_service_deletion_delay() -> int:
    """
    Returns the delay in seconds for fast service deletion.
    This is used to speed up tests that involve service deletion.
    """
    return 1


@pytest.fixture
def app_environment(
    fast_service_deletion_delay: int,
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
) -> EnvVarsDict:
    # NOTE: undos some app_environment settings
    monkeypatch.delenv("WEBSERVER_GARBAGE_COLLECTOR", raising=False)
    app_environment.pop("WEBSERVER_GARBAGE_COLLECTOR", None)

    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_COMPUTATION": "1",
            "WEBSERVER_NOTIFICATIONS": "1",
            # sets TTL of a resource after logout
            "RESOURCE_MANAGER_RESOURCE_TTL_S": f"{fast_service_deletion_delay}",
            "GARBAGE_COLLECTOR_INTERVAL_S": "30",
        },
    )
