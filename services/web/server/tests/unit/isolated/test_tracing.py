# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module


import pytest
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp.tracing import aiohttp_server_opentelemetry_middleware
from servicelib.tracing import TracingConfig
from simcore_service_webserver._meta import APP_NAME
from simcore_service_webserver.application import create_application
from simcore_service_webserver.application_settings import ApplicationSettings


@pytest.fixture
def mock_webserver_service_environment(
    monkeypatch: pytest.MonkeyPatch, mock_webserver_service_environment: EnvVarsDict
) -> EnvVarsDict:
    monkeypatch.delenv("WEBSERVER_TRACING")

    return mock_webserver_service_environment | setenvs_from_dict(
        monkeypatch,
        {
            "TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT": "http://opentelemetry-collector",
            "TRACING_OPENTELEMETRY_COLLECTOR_PORT": "4318",
        },
    )


def test_middleware_restrictions_opentelemetry_is_second_middleware(
    mock_webserver_service_environment: EnvVarsDict,
):
    settings = ApplicationSettings.create_from_envs()
    assert settings.WEBSERVER_TRACING
    tracing_config = TracingConfig.create(service_name=APP_NAME, tracing_settings=settings.WEBSERVER_TRACING)

    app = create_application(tracing_config=tracing_config)
    assert app.middlewares
    assert app.middlewares[0] is aiohttp_server_opentelemetry_middleware
