# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import httpx
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_messages import LoggerRabbitMessage
from models_library.users import UserID
from pydantic import parse_obj_as
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


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return parse_obj_as(UserID, faker.pyint())


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return parse_obj_as(ProjectID, faker.uuid4())


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return parse_obj_as(NodeID, faker.uuid4())


async def test_subscribe_publish_receive_logs(
    client: httpx.AsyncClient,
    app: FastAPI,
    faker: Faker,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
):
    _comsumer_message_handler = AsyncMock(return_value=True)

    # create consumer & subscribe
    rabbit_consumer: RabbitMQClient = get_rabbitmq_client(app)
    queue_name = await rabbit_consumer.subscribe(
        LoggerRabbitMessage.get_channel_name(),
        _comsumer_message_handler,
        exclusive_queue=False,  # this instance should receive the incoming messages
        topics=[f"{project_id}.*"],
    )

    # log producer
    rabbitmq_producer = create_rabbitmq_client("pytest_producer")
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
    await rabbit_consumer.remove_topics(queue_name, topics=[f"{project_id}.*"])


@asynccontextmanager
async def rabbit_consuming_context(app: FastAPI):
    _comsumer_message_handler = AsyncMock(return_value=True)

    rabbit_consumer: RabbitMQClient = get_rabbitmq_client(app)
    queue_name = await rabbit_consumer.subscribe(
        LoggerRabbitMessage.get_channel_name(),
        _comsumer_message_handler,
        exclusive_queue=False,  # this instance should receive the incoming messages
        topics=[f"{project_id}.*"],
    )

    yield _comsumer_message_handler

    await rabbit_consumer.remove_topics(queue_name, topics=[f"{project_id}.*"])


async def test_multiple_producers_and_single_consumer(
    client: httpx.AsyncClient,
    app: FastAPI,
    faker: Faker,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
):

    async with rabbit_consuming_context(app) as consumer_message_handler:
        # multiple producers
        async def _produce_logs(name, project_id_=None, node_id_=None, messages_=None):
            rabbitmq_producer = create_rabbitmq_client(f"pytest_producer_{name}")
            log_message = LoggerRabbitMessage(
                user_id=user_id,
                project_id=project_id_ or faker.uuid4(),
                node_id=node_id_,
                messages=messages_ or [faker.text() for _ in range(10)],
            )
            await rabbitmq_producer.publish(log_message.channel_name, log_message)

        asyncio.gather(
            *[
                _produce_logs(
                    "expected", project_id, node_id, ["expected message"] * 3
                ),
                *(_produce_logs(f"{n}") for n in range(5)),
            ]
        )

    # check it received
    await asyncio.sleep(1)
    assert consumer_message_handler.await_count == 1
    (data,) = consumer_message_handler.call_args[0]
    assert isinstance(data, bytes)
    received_message = LoggerRabbitMessage.parse_raw(data)

    assert received_message.user_id == user_id
    assert received_message.project_id == project_id
    assert received_message.node_id == node_id
    assert received_message.messages == ["expected message"] * 3
