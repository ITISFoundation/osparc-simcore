# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import logging
from collections.abc import AsyncIterable, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Final, Iterable
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from faker import Faker
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.rabbitmq_messages import LoggerRabbitMessage
from models_library.users import UserID
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_envs import (
    EnvVarsDict,
    delenvs_from_dict,
    setenvs_from_dict,
)
from servicelib.fastapi.rabbitmq import get_rabbitmq_client
from servicelib.rabbitmq import RabbitMQClient
from simcore_service_api_server.api.dependencies.rabbitmq import LogListener
from simcore_service_api_server.models.schemas.jobs import JobLog
from simcore_service_api_server.services.director_v2 import (
    ComputationTaskGet,
    DirectorV2Api,
)

pytest_simcore_core_services_selection = [
    "rabbit",
]
pytest_simcore_ops_services_selection = []

_logger = logging.getLogger()
_faker: Faker = Faker()


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    rabbit_env_vars_dict: EnvVarsDict,
    mocker: MockerFixture,
) -> EnvVarsDict:
    # do not init other services
    mocker.stopall()
    mocker.patch("simcore_service_api_server.core.application.webserver.setup")
    mocker.patch("simcore_service_api_server.core.application.catalog.setup")
    mocker.patch("simcore_service_api_server.core.application.storage.setup")

    delenvs_from_dict(monkeypatch, ["API_SERVER_RABBITMQ"])
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
    async def _consumer_message_handler(data, **kwargs):
        _consumer_message_handler.called = True
        _consumer_message_handler.data = data
        _ = LoggerRabbitMessage.parse_raw(data)
        return True

    # create consumer & subscribe
    rabbit_consumer: RabbitMQClient = get_rabbitmq_client(app)
    queue_name = await rabbit_consumer.subscribe(
        LoggerRabbitMessage.get_channel_name(),
        _consumer_message_handler,
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
    _consumer_message_handler.called = False
    _consumer_message_handler.data = None
    await rabbitmq_producer.publish(log_message.channel_name, log_message)

    # check it received
    await asyncio.sleep(1)

    assert _consumer_message_handler.called
    data = _consumer_message_handler.data
    assert isinstance(data, bytes)
    assert LoggerRabbitMessage.parse_raw(data) == log_message

    # unsuscribe
    await rabbit_consumer.remove_topics(queue_name, topics=[f"{project_id}.*"])


@asynccontextmanager
async def rabbit_consuming_context(
    app: FastAPI,
    project_id: ProjectID,
) -> AsyncIterable[AsyncMock]:
    consumer_message_handler = AsyncMock(return_value=True)

    rabbit_consumer: RabbitMQClient = get_rabbitmq_client(app)
    queue_name = await rabbit_consumer.subscribe(
        LoggerRabbitMessage.get_channel_name(),
        consumer_message_handler,
        exclusive_queue=True,
        topics=[f"{project_id}.*"],
    )

    yield consumer_message_handler

    await rabbit_consumer.unsubscribe(queue_name)


@pytest.fixture
def produce_logs(
    faker: Faker,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    user_id: UserID,
):
    async def _go(name, project_id_=None, node_id_=None, messages_=None, level_=None):
        rabbitmq_producer = create_rabbitmq_client(f"pytest_producer_{name}")
        log_message = LoggerRabbitMessage(
            user_id=user_id,
            project_id=project_id_ or faker.uuid4(),
            node_id=node_id_,
            messages=messages_ or [faker.text() for _ in range(10)],
            log_level=level_ or logging.INFO,
        )
        await rabbitmq_producer.publish(log_message.channel_name, log_message)

    return _go


async def test_multiple_producers_and_single_consumer(
    client: httpx.AsyncClient,
    app: FastAPI,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    produce_logs: Callable,
):
    await produce_logs("lost", project_id)

    async with rabbit_consuming_context(app, project_id) as consumer_message_handler:
        # multiple producers
        asyncio.gather(
            *[
                produce_logs("expected", project_id, node_id, ["expected message"] * 3),
                *(produce_logs(f"{n}") for n in range(5)),
            ]
        )
        await asyncio.sleep(1)

    # check it received
    assert consumer_message_handler.await_count == 1
    (data,) = consumer_message_handler.call_args[0]
    assert isinstance(data, bytes)
    received_message = LoggerRabbitMessage.parse_raw(data)

    assert received_message.user_id == user_id
    assert received_message.project_id == project_id
    assert received_message.node_id == node_id
    assert received_message.messages == ["expected message"] * 3


#
# --------------------
#


@pytest.fixture
def computation_done() -> Iterable[Callable[[], bool]]:
    stop_time: Final[datetime] = datetime.now() + timedelta(seconds=5)

    def _job_done() -> bool:
        return datetime.now() >= stop_time

    yield _job_done


@pytest.fixture
async def log_listener(
    client: httpx.AsyncClient,
    app: FastAPI,
    project_id: ProjectID,
    user_id: UserID,
    mocked_directorv2_service_api_base: respx.MockRouter,
    computation_done: Callable[[], bool],
) -> AsyncIterable[LogListener]:
    def _get_computation(request: httpx.Request, **kwargs) -> httpx.Response:
        task = ComputationTaskGet.parse_obj(
            ComputationTaskGet.Config.schema_extra["examples"][0]
        )
        if computation_done():
            task.state = RunningState.SUCCESS
            task.stopped = datetime.now()
        return httpx.Response(
            status_code=status.HTTP_200_OK, json=jsonable_encoder(task)
        )

    mocked_directorv2_service_api_base.get(f"/v2/computations/{project_id}").mock(
        side_effect=_get_computation
    )

    assert isinstance(d2_client := DirectorV2Api.get_instance(app), DirectorV2Api)
    log_listener: LogListener = LogListener(
        user_id=user_id,
        rabbit_consumer=get_rabbitmq_client(app),
        director2_api=d2_client,
    )
    await log_listener.listen(project_id)
    yield log_listener


async def test_log_listener(
    client: httpx.AsyncClient,
    app: FastAPI,
    project_id: ProjectID,
    node_id: NodeID,
    produce_logs: Callable,
    log_listener: LogListener,
    faker: Faker,
    computation_done: Callable[[], bool],
):
    published_logs: list[str] = []

    async def _log_publisher():
        while not computation_done():
            msg: str = faker.text()
            await asyncio.sleep(faker.pyfloat(min_value=0.0, max_value=5.0))
            await produce_logs("expected", project_id, node_id, [msg], logging.DEBUG)
            published_logs.append(msg)

    publish_task = asyncio.create_task(_log_publisher())

    collected_messages: list[str] = []
    async for log in log_listener.log_generator():
        job_log: JobLog = JobLog.parse_raw(log)
        assert len(job_log.messages) == 1
        assert job_log.job_id == project_id
        collected_messages.append(job_log.messages[0])

    publish_task.cancel()
    assert len(published_logs) > 0
    assert published_logs == collected_messages
