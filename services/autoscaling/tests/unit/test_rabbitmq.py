# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from fastapi import FastAPI
from settings_library.rabbit import RabbitSettings

# Selection of core and tool services started in this swarm fixture (integration)
pytest_simcore_core_services_selection = [
    "rabbit",
]

pytest_simcore_ops_services_selection = []


def test_rabbitmq_does_not_initialize_if_deactivated(
    disabled_rabbitmq, initialized_app: FastAPI
):
    assert hasattr(initialized_app.state, "rabbitmq_client")
    assert initialized_app.state.rabbitmq_client == None


def test_rabbitmq_initializes(
    enabled_rabbitmq: RabbitSettings, initialized_app: FastAPI
):
    assert hasattr(initialized_app.state, "rabbitmq_client")
    assert initialized_app.state.rabbitmq_client is not None
