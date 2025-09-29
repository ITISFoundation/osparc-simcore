# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict


@pytest.fixture(scope="session")
def service_name() -> str:
    # Overrides  service_name fixture needed in docker_compose_service_environment_dict fixture
    return "webserver"


@pytest.fixture
def app_environment(
    app_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    # NOTE: overrides app_environment
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_FUNCTIONS": "0",  # needs rabbitmq
        },
    )
