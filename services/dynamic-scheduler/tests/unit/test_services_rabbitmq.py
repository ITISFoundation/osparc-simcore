# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


import pytest
from fastapi import FastAPI
from models_library.rabbitmq_messages import RabbitMessageBase
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from simcore_service_dynamic_scheduler.services.rabbitmq import (
    get_rabbitmq_client,
    get_rabbitmq_rpc_server,
    post_message,
)

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def app_environment(
    disable_redis_lifespan: None,
    disable_service_tracker_lifespan: None,
    disable_deferred_manager_lifespan: None,
    disable_notifier_lifespan: None,
    disable_status_monitor_lifespan: None,
    app_environment: EnvVarsDict,
    rabbit_service: RabbitSettings,
) -> EnvVarsDict:
    return app_environment


async def test_health(app: FastAPI):
    assert get_rabbitmq_client(app)
    assert get_rabbitmq_rpc_server(app)

    class TestMessage(RabbitMessageBase):
        channel_name: str = "test"

        # pylint:disable=no-self-use
        def routing_key(self) -> str | None:
            return None

    await post_message(app, TestMessage())
