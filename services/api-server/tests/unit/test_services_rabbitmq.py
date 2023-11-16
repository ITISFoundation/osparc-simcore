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
from typing import Annotated
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from faker import Faker
from fastapi import Depends, FastAPI
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
from starlette.background import BackgroundTask

pytest_simcore_core_services_selection = [
    "rabbit",
]
pytest_simcore_ops_services_selection = []

_NEW_LINE = "\n"
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


class JobLog(BaseModel):
    job_id: ProjectID
    node_id: NodeID | None
    log_level: LogLevelInt
    messages: list[LogMessageStr]


class LogListener:
    _queue: Queue[JobLog]
    _queu_name: str
    _rabbit_consumer: RabbitMQClient

    @classmethod
    async def create(
        cls,
        rabbit_consumer: RabbitMQClient,
        project_id: UUID,
        job_logs: list[JobLog] = [],
    ) -> "LogListener":
        self = cls()
        self._queue = Queue()
        for job_log in job_logs:
            await self._queue.put(job_log)
        self._rabbit_consumer = rabbit_consumer
        self._queu_name = await self._rabbit_consumer.subscribe(
            LoggerRabbitMessage.get_channel_name(),
            self._add_logs_to_queu,
            exclusive_queue=True,
            topics=[f"{project_id}.*"],
        )
        return self

    def unsubscribe_task(self) -> BackgroundTask:
        return BackgroundTask(self._rabbit_consumer.unsubscribe, self._queu_name)

    async def _add_logs_to_queu(self, data: bytes):
        got = LoggerRabbitMessage.parse_raw(data)
        item = JobLog(
            job_id=got.project_id,
            node_id=got.node_id,
            log_level=got.log_level,
            messages=got.messages,
        )
        await self._queue.put(item)
        return True

    async def log_generator(self) -> AsyncIterable[str]:
        n_logs: int = 0
        while n_logs < 10:
            log: JobLog = await self._queue.get()
            yield log.json() + _NEW_LINE
            n_logs += 1


@pytest.fixture
async def log_listener(
    client: httpx.AsyncClient, app: FastAPI, project_id: ProjectID
) -> AsyncIterable[LogListener]:
    rabbit_consumer: RabbitMQClient = get_rabbitmq_client(app)
    yield await LogListener.create(rabbit_consumer, project_id)


async def test_json_log_generator(
    client: httpx.AsyncClient,
    app: FastAPI,
    project_id: ProjectID,
    node_id: NodeID,
    produce_logs: Callable,
    log_listener: LogListener,
    faker: Faker,
):
    async def _log_publisher(n_logs: int) -> list[str]:
        logs = []
        for ii in range(n_logs):
            msg: str = faker.text()
            await asyncio.sleep(faker.pyfloat(min_value=0.0, max_value=5.0))
            await produce_logs("expected", project_id, node_id, [msg], logging.DEBUG)
            logs.append(msg)
        return logs

    n_logs: int = 5
    task = asyncio.create_task(_log_publisher(n_logs))

    ii: int = 0
    collected_messages: list[str] = []
    async for log in log_listener.log_generator():
        job_log: JobLog = JobLog.parse_raw(log)
        assert len(job_log.messages) == 1
        assert job_log.job_id == project_id
        collected_messages.append(job_log.messages[0])
        ii += 1
        if ii == n_logs:
            break

    assert task.done()
    assert task.result() == collected_messages


@pytest.fixture
async def fake_logger_injected(client: httpx.AsyncClient, app: FastAPI):
    @app.get("/projects/{project_id}/logs")
    async def _stream_logs_handler(
        project_id: ProjectID,
    ):
        async def _fake_log_generator() -> AsyncIterable[str]:
            for ii in range(100):
                job_log: JobLog = JobLog(
                    job_id=project_id,
                    node_id=_faker.uuid4(),
                    log_level=logging.INFO,
                    messages=[f"message#={ii}"],
                )
                yield job_log.json() + _NEW_LINE

        return StreamingResponse(_fake_log_generator(), media_type="application/json")


async def test_fake_logging_endpoint(
    app: FastAPI,
    client: httpx.AsyncClient,
    project_id: ProjectID,
    fake_logger_injected: None,
):
    async with client.stream("GET", f"/projects/{project_id}/logs") as r:
        # streams open
        ii: int = 0
        async for line in r.aiter_lines():
            data = json.loads(line)
            log = JobLog.parse_obj(data)
            assert log.job_id == project_id
            assert len(log.messages) == 1
            assert log.messages[0] == f"message#={ii}"
            ii += 1
            _logger.info(log.json(indent=3))


@pytest.fixture
async def new_routes_injected(client: httpx.AsyncClient, app: FastAPI):
    @app.get("/projects/{project_id}/logs")
    async def _stream_logs_handler(
        project_id: ProjectID,
        *,
        rabbit_consumer: Annotated[RabbitMQClient, Depends(get_rabbitmq_client)],
    ):
        inital_job_logs: list[JobLog] = [
            JobLog(
                job_id=_faker.uuid4(),
                node_id=_faker.uuid4(),
                log_level=logging.DEBUG,
                messages=["initial message"],
            )
            for _ in range(100)
        ]

        log_listener: LogListener = await LogListener.create(
            rabbit_consumer, project_id, job_logs=inital_job_logs
        )
        return StreamingResponse(
            log_listener.log_generator(),
        )


async def test_stream_logs(
    #    app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    node_id: NodeID,
    project_id: ProjectID,
    produce_logs: Callable,
    new_routes_injected: None,
):
    # coro = produce_logs(
    #     "expected", project_id, node_id, ["expected message"], logging.DEBUG
    # )

    # n_tasks: int = 3
    # tasks = [asyncio.create_task(coro, name="log-producer") for _ in range(n_tasks)]
    # asyncio.gather(*tasks)

    n_count: int = 0
    async with client.stream("GET", f"/projects/{project_id}/logs") as r:
        # streams open
        async for line in r.aiter_lines():
            data = json.loads(line)
            log = JobLog.parse_obj(data)
            # assert log.job_id == project_id
            assert log.log_level == logging.DEBUG

            _logger.info(log.json(indent=3))
            n_count += 1
    assert n_count > 0
