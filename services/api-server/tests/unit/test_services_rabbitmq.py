# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import json
import logging
from asyncio import Queue
from collections.abc import AsyncIterable, Callable
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from faker import Faker
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_messages import LoggerRabbitMessage
from models_library.users import UserID
from pydantic import BaseModel, parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from servicelib.logging_utils import LogLevelInt, LogMessageStr
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
async def rabbit_consuming_context(
    app: FastAPI,
    project_id: ProjectID,
    comsumer_message_handler: Callable | None = None,
):
    if not comsumer_message_handler:
        comsumer_message_handler = AsyncMock(return_value=True)

    rabbit_consumer: RabbitMQClient = get_rabbitmq_client(app)
    queue_name = await rabbit_consumer.subscribe(
        LoggerRabbitMessage.get_channel_name(),
        comsumer_message_handler,
        exclusive_queue=True,
        topics=[f"{project_id}.*"],
    )

    yield comsumer_message_handler

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


#
# --------------------
#


class JobLog(BaseModel):
    job_id: ProjectID
    node_id: NodeID | None
    log_level: LogLevelInt
    messages: list[LogMessageStr]


@pytest.fixture
def new_routes_injected(app: FastAPI):
    # https://docs.python.org/3/library/asyncio-queue.html#queue

    _NEW_LINE = "\n"

    async def _json_logs_generator(project_id: UUID) -> AsyncIterable[str]:
        log_queu: Queue[JobLog] = Queue(maxsize=50)

        async def _add_logs_to_queu(data: bytes):
            got = LoggerRabbitMessage.parse_raw(data)
            assert got.project_id == project_id

            item = JobLog(
                job_id=got.project_id,
                node_id=got.node_id,
                log_level=got.log_level,
                messages=got.messages,
            )
            await log_queu.put(item)
            return True

        # listen to project_id
        rabbit_consumer: RabbitMQClient = get_rabbitmq_client(app)
        queue_name = await rabbit_consumer.subscribe(
            LoggerRabbitMessage.get_channel_name(),
            _add_logs_to_queu,
            exclusive_queue=True,
            topics=[f"{project_id}.*"],
        )

        while True:
            log: JobLog = await log_queu.get()
            yield log.json() + _NEW_LINE

    @app.get("/projects/{project_id}/logs")
    async def _stream_logs_handler(project_id: ProjectID, *, follow: bool = False):
        return StreamingResponse(
            _json_logs_generator(project_id),
            media_type="application/x-ndjson",
        )


async def test_stream_logs(
    new_routes_injected: None,
    app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    node_id: NodeID,
    project_id: ProjectID,
    produce_logs: Callable,
):

    coro = produce_logs(
        "expected", project_id, node_id, ["expected message"], logging.DEBUG
    )

    n_tasks: int = 3
    tasks = [asyncio.create_task(coro, name="log-producer") for _ in range(n_tasks)]

    n_count: int = 0
    async with client.stream("GET", f"/projects/{project_id}/logs") as r:
        # streams open
        async for line in r.aiter_lines():
            data = json.loads(line)
            log = JobLog.parse_obj(data)
            assert log.job_id == project_id
            assert log.log_level == logging.DEBUG
            assert log.messages == ["expected message"]

            print(log.json(indent=3))
            n_count += 1
    assert n_count == n_tasks
