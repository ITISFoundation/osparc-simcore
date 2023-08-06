# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from fastapi import FastAPI
from settings_library.rabbit import RabbitSettings
from simcore_service_resource_usage_tracker.core.errors import ConfigurationError
from simcore_service_resource_usage_tracker.modules.rabbitmq import get_rabbitmq_client

# Selection of core and tool services started in this swarm fixture (integration)
pytest_simcore_core_services_selection = [
    "rabbit",
]

pytest_simcore_ops_services_selection = []


def test_rabbitmq_does_not_initialize_if_deactivated(
    disabled_prometheus: None,
    disabled_database: None,
    disabled_rabbitmq: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
):
    assert hasattr(initialized_app.state, "rabbitmq_client")
    assert initialized_app.state.rabbitmq_client == None
    with pytest.raises(ConfigurationError):
        get_rabbitmq_client(initialized_app)


def test_rabbitmq_initializes(
    disabled_prometheus: None,
    disabled_database: None,
    enabled_rabbitmq: RabbitSettings,
    mocked_redis_server: None,
    initialized_app: FastAPI,
):
    assert hasattr(initialized_app.state, "rabbitmq_client")
    assert initialized_app.state.rabbitmq_client is not None
    assert get_rabbitmq_client(initialized_app) == initialized_app.state.rabbitmq_client
