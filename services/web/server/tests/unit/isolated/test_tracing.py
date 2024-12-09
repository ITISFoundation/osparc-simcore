# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module


import pytest
from opentelemetry.instrumentation.aiohttp_server import (
    middleware as aiohttp_opentelemetry_middleware,
)
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_webserver.application import create_application
from simcore_service_webserver.application_settings import ApplicationSettings


@pytest.fixture
def mock_webserver_service_environment(
    monkeypatch: pytest.MonkeyPatch, mock_webserver_service_environment: EnvVarsDict
) -> EnvVarsDict:

    envs = mock_webserver_service_environment | setenvs_from_dict(
        monkeypatch,
        {
            "TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT": "http://opentelemetry-collector",
            "TRACING_OPENTELEMETRY_COLLECTOR_PORT": "4318",
        },
    )

    envs.pop("WEBSERVER_TRACING")

    return envs


def test_middleware_restrictions_opentelemetry_is_second_middleware(
    mock_webserver_service_environment: EnvVarsDict,
):
    settings = ApplicationSettings.create_from_envs()
    assert settings.WEBSERVER_TRACING

    app = create_application()
    assert app.middlewares
    assert (
        app.middlewares[0].__middleware_name__
        == "servicelib.aiohttp.monitoring.monitor_simcore_service_webserver"
    )
    assert app.middlewares[1] is aiohttp_opentelemetry_middleware
