# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock

import httpx
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.rabbitmq_messages import LoggerRabbitMessage
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from servicelib.rabbitmq import RabbitMQClient
from simcore_service_api_server.services.rabbitmq import get_rabbitmq_client

pytest_simcore_core_services_selection = [
    "rabbit",
]
pytest_simcore_ops_services_selection = []


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    rabbit_env_vars_dict: EnvVarsDict,
    mocker: MockerFixture,
) -> EnvVarsDict:
    # do not init other services
    mocker.patch("simcore_service_api_server.core.application.webserver.setup")
    mocker.patch("simcore_service_api_server.core.application.catalog.setup")
    mocker.patch("simcore_service_api_server.core.application.storage.setup")
    mocker.patch("simcore_service_api_server.core.application.director_v2.setup")

    return setenvs_from_dict(
        monkeypatch,
        {
            **rabbit_env_vars_dict,
            "API_SERVER_POSTGRES": "null",
        },
    )


async def test_it(
    client: httpx.AsyncClient,
    app: FastAPI,
    faker: Faker,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
):
    # create exchange
    # create producer
    rabbitmq_producer = create_rabbitmq_client("pytest_producer")

    # create consumer & subscribe
    rabbit_client: RabbitMQClient = get_rabbitmq_client(app)

    project_id = faker.uuid4()
    user_id = faker.pyint()
    node_id = faker.uuid4()
    exchange_name = LoggerRabbitMessage.get_channel_name()
    topics = [f"{project_id}.*"]

    _comsumer_message_handler = AsyncMock(return_value=True)

    await rabbit_client.subscribe(
        exchange_name,
        _comsumer_message_handler,
        exclusive_queue=False,  # this instance should receive the incoming messages
        topics=topics,
    )

    # produce log
    log_message = LoggerRabbitMessage(
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        messages=[faker.text() for _ in range(10)],
    )
    await rabbitmq_producer.publish(log_message.channel_name, log_message)

    # check it received

    await asyncio.sleep(1)

    assert _comsumer_message_handler.await_count
    (data,) = _comsumer_message_handler.call_args[0]
    assert isinstance(data, bytes)
    assert LoggerRabbitMessage.parse_raw(data) == log_message

    # unsuscribe
    await rabbit_client.remove_topics(exchange_name, topics=topics)
