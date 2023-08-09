# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from unittest import mock

import asgi_lifespan
import pytest
from fastapi import FastAPI
from pytest_mock import MockerFixture
from requests_mock.mocker import Mocker
from simcore_service_resource_usage_tracker.core.application import create_app
from simcore_service_resource_usage_tracker.core.errors import ConfigurationError
from simcore_service_resource_usage_tracker.core.settings import ApplicationSettings
from simcore_service_resource_usage_tracker.modules.prometheus import (
    get_prometheus_api_client,
)


@pytest.fixture
def mocked_prometheus_fail_response(
    requests_mock: Mocker, app_settings: ApplicationSettings
) -> None:
    assert app_settings.RESOURCE_USAGE_TRACKER_PROMETHEUS
    requests_mock.get(
        f"{app_settings.RESOURCE_USAGE_TRACKER_PROMETHEUS.api_url}/",
        status_code=401,
    )


def test_prometheus_does_not_initialize_if_deactivated(
    disabled_database: None,
    disabled_prometheus: None,
    disabled_rabbitmq: None,
    mocked_setup_rabbitmq: mock.Mock,
    mocked_redis_server: None,
    initialized_app: FastAPI,
):
    assert hasattr(initialized_app.state, "prometheus_api_client")
    assert initialized_app.state.prometheus_api_client is None

    with pytest.raises(ConfigurationError):
        get_prometheus_api_client(initialized_app)


def test_mocked_prometheus_initialize(
    disabled_database,
    disabled_rabbitmq: None,
    mocked_prometheus: None,
    mocked_redis_server: None,
    mocked_setup_rabbitmq: mock.Mock,
    initialized_app: FastAPI,
):
    assert get_prometheus_api_client(initialized_app)


async def test_prometheus_raises_on_init_if_connection_returns_not_ok(
    mocked_prometheus_fail_response: None, app_settings: ApplicationSettings
):
    app = create_app(app_settings)
    with pytest.raises(ConfigurationError):
        async with asgi_lifespan.LifespanManager(app):
            ...


async def test_prometheus_raises_on_init_if_no_prometheus_reached(
    app_settings: ApplicationSettings, mocker: MockerFixture
):
    app = create_app(app_settings)
    with pytest.raises(TimeoutError):
        # NOTE: this ensures the code for retrying connection to prometheus is hit
        async with asgi_lifespan.LifespanManager(app, startup_timeout=10):
            ...
