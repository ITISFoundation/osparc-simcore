# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=R6301

import asyncio
import logging
import random
from collections.abc import AsyncIterable, Callable, Iterable
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Final, Literal
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
import respx
from attr import dataclass
from faker import Faker
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.rabbitmq_messages import LoggerRabbitMessage, RabbitMessageBase
from models_library.users import UserID
from pydantic import ValidationError
from pytest_mock import MockerFixture, MockFixture
from pytest_simcore.helpers.monkeypatch_envs import (
    EnvVarsDict,
    delenvs_from_dict,
    setenvs_from_dict,
)
from servicelib.rabbitmq import RabbitMQClient
from simcore_service_api_server.api.dependencies.rabbitmq import get_log_distributor
from simcore_service_api_server.core.health_checker import get_health_checker
from simcore_service_api_server.models.schemas.jobs import JobID, JobLog
from simcore_service_api_server.services.director_v2 import (
    ComputationTaskGet,
    DirectorV2Api,
)
from simcore_service_api_server.services.log_streaming import (
    LogDistributor,
    LogStreamer,
    LogStreamerRegistrationConflictError,
)
from tenacity import AsyncRetrying, retry_if_not_exception_type, stop_after_delay

pytest_simcore_core_services_selection = [
    "rabbit",
]
pytest_simcore_ops_services_selection = []


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    rabbit_env_vars_dict: EnvVarsDict,
) -> EnvVarsDict:
    # do not init other services
    delenvs_from_dict(monkeypatch, ["API_SERVER_RABBITMQ"])
    return setenvs_from_dict(
        monkeypatch,
        {
            **rabbit_env_vars_dict,
            "API_SERVER_POSTGRES": "null",
            "API_SERVER_HEALTH_CHECK_TASK_PERIOD_SECONDS": "3",
            "API_SERVER_HEALTH_CHECK_TASK_TIMEOUT_SECONDS": "1",
        },
    )


@pytest.fixture
def mock_missing_plugins(app_environment: EnvVarsDict, mocker: MockerFixture):
    mocker.patch("simcore_service_api_server.core.application.webserver.setup")
    mocker.patch("simcore_service_api_server.core.application.catalog.setup")
    mocker.patch("simcore_service_api_server.core.application.storage.setup")


@pytest.fixture
async def log_distributor(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
) -> AsyncIterable[LogDistributor]:
    log_distributor = LogDistributor(create_rabbitmq_client("log_distributor_client"))
    await log_distributor.setup()
    yield log_distributor
    await log_distributor.teardown()


async def test_subscribe_publish_receive_logs(
    faker: Faker,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    log_distributor: LogDistributor,
    mocker: MockerFixture,
):
    @dataclass
    class MockQueue:
        called: bool = False
        job_log: JobLog | None = None

        async def put(self, job_log: JobLog):
            self.called = True
            self.job_log = job_log
            assert isinstance(job_log, JobLog)

    mock_queue = MockQueue()
    await log_distributor.register(project_id, mock_queue)  # type: ignore

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
    await log_distributor.deregister(project_id)

    assert mock_queue.called
    job_log = mock_queue.job_log
    assert isinstance(job_log, JobLog)
    assert job_log.job_id == log_message.project_id


@asynccontextmanager
async def _rabbit_consuming_context(
    app: FastAPI,
    project_id: ProjectID,
) -> AsyncIterable[AsyncMock]:

    queue = asyncio.Queue()
    queue.put = AsyncMock()
    log_distributor: LogDistributor = get_log_distributor(app)
    await log_distributor.register(project_id, queue)

    yield queue.put

    await log_distributor.deregister(project_id)


@pytest.fixture
def produce_logs(
    faker: Faker,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    user_id: UserID,
):
    async def _go(
        name,
        project_id_=None,
        node_id_=None,
        messages_=None,
        level_=None,
        log_message: RabbitMessageBase | None = None,
    ):
        rabbitmq_producer = create_rabbitmq_client(f"pytest_producer_{name}")
        if log_message is None:
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

    async with _rabbit_consuming_context(app, project_id) as consumer_message_handler:
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
    (job_log,) = consumer_message_handler.call_args[0]
    assert isinstance(job_log, JobLog)

    assert job_log.job_id == project_id
    assert job_log.node_id == node_id
    assert job_log.messages == ["expected message"] * 3


#
# --------------------
#


async def test_one_job_multiple_registrations(
    log_distributor: LogDistributor, project_id: ProjectID
):
    async def _(job_log: JobLog):
        pass

    await log_distributor.register(project_id, _)
    with pytest.raises(LogStreamerRegistrationConflictError):
        await log_distributor.register(project_id, _)
    await log_distributor.deregister(project_id)


async def test_log_distributor_register_deregister(
    project_id: ProjectID,
    node_id: NodeID,
    log_distributor: LogDistributor,
    produce_logs: Callable,
    faker: Faker,
):
    collected_logs: list[str] = []

    class MockQueue:
        async def put(self, job_log: JobLog):
            for msg in job_log.messages:
                collected_logs.append(msg)

    queue = MockQueue()
    published_logs: list[str] = []

    async def _log_publisher():
        for _ in range(5):
            msg: str = faker.text()
            await asyncio.sleep(0.1)
            await produce_logs("expected", project_id, node_id, [msg], logging.DEBUG)
            published_logs.append(msg)

    await log_distributor.register(project_id, queue)  # type: ignore
    publisher_task = asyncio.create_task(_log_publisher())
    await asyncio.sleep(0.1)
    await log_distributor.deregister(project_id)
    await asyncio.sleep(0.1)
    await log_distributor.register(project_id, queue)  # type: ignore
    await asyncio.gather(publisher_task)
    await asyncio.sleep(0.5)
    await log_distributor.deregister(project_id)

    assert len(log_distributor._log_streamers.keys()) == 0
    assert len(collected_logs) > 0
    assert set(collected_logs).issubset(
        set(published_logs)
    )  # some logs might get lost while being deregistered


async def test_log_distributor_multiple_streams(
    project_id: ProjectID,
    node_id: NodeID,
    log_distributor: LogDistributor,
    produce_logs: Callable,
    faker: Faker,
):
    job_ids: Final[list[JobID]] = [JobID(faker.uuid4()) for _ in range(2)]

    collected_logs: dict[JobID, list[str]] = {id_: [] for id_ in job_ids}

    class MockQueue:
        async def put(self, job_log: JobLog):
            job_id = job_log.job_id
            assert (msgs := collected_logs.get(job_id)) is not None
            for msg in job_log.messages:
                msgs.append(msg)

    queue = MockQueue()
    published_logs: dict[JobID, list[str]] = {id_: [] for id_ in job_ids}

    async def _log_publisher():
        for _ in range(5):
            msg: str = faker.text()
            await asyncio.sleep(0.1)
            job_id: JobID = random.choice(job_ids)
            await produce_logs("expected", job_id, node_id, [msg], logging.DEBUG)
            published_logs[job_id].append(msg)

    for job_id in job_ids:
        await log_distributor.register(job_id, queue)  # type: ignore
    publisher_task = asyncio.create_task(_log_publisher())
    await asyncio.gather(publisher_task)
    await asyncio.sleep(0.5)
    for job_id in job_ids:
        await log_distributor.deregister(job_id)
    for key in collected_logs:
        assert key in published_logs
        assert collected_logs[key] == published_logs[key]


#
# --------------------
#


@pytest.fixture
def computation_done() -> Iterable[Callable[[], bool]]:
    stop_time: Final[datetime] = datetime.now() + timedelta(seconds=2)

    def _job_done() -> bool:
        return datetime.now() >= stop_time

    return _job_done


@pytest.fixture
async def log_streamer_with_distributor(
    client: httpx.AsyncClient,
    app: FastAPI,
    project_id: ProjectID,
    user_id: UserID,
    mocked_directorv2_service_api_base: respx.MockRouter,
    computation_done: Callable[[], bool],
    log_distributor: LogDistributor,
) -> AsyncIterable[LogStreamer]:
    def _get_computation(request: httpx.Request, **kwargs) -> httpx.Response:
        task = ComputationTaskGet.model_validate(
            ComputationTaskGet.model_config["json_schema_extra"]["examples"][0]
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
    yield LogStreamer(
        user_id=user_id,
        director2_api=d2_client,
        job_id=project_id,
        log_distributor=log_distributor,
        log_check_timeout=1,
    )

    assert len(log_distributor._log_streamers.keys()) == 0


async def test_log_streamer_with_distributor(
    project_id: ProjectID,
    node_id: NodeID,
    produce_logs: Callable,
    log_streamer_with_distributor: LogStreamer,
    faker: Faker,
    computation_done: Callable[[], bool],
):
    published_logs: list[str] = []

    async def _log_publisher():
        while not computation_done():
            msg: str = faker.text()
            await produce_logs("expected", project_id, node_id, [msg], logging.DEBUG)
            published_logs.append(msg)

    publish_task = asyncio.create_task(_log_publisher())

    collected_messages: list[str] = []
    async for log in log_streamer_with_distributor.log_generator():
        job_log: JobLog = JobLog.model_validate_json(log)
        assert len(job_log.messages) == 1
        assert job_log.job_id == project_id
        collected_messages.append(job_log.messages[0])

    if not publish_task.done():
        publish_task.cancel()
        try:
            await publish_task
        except asyncio.CancelledError:
            pass

    assert len(published_logs) > 0
    assert published_logs == collected_messages


async def test_log_streamer_not_raise_with_distributor(
    user_id,
    project_id: ProjectID,
    node_id: NodeID,
    produce_logs: Callable,
    log_streamer_with_distributor: LogStreamer,
    faker: Faker,
    computation_done: Callable[[], bool],
):
    class InvalidLoggerRabbitMessage(LoggerRabbitMessage):
        channel_name: Literal["simcore.services.logs.v2"] = "simcore.services.logs.v2"
        node_id: NodeID | None
        messages: int
        log_level: int = logging.INFO

        def routing_key(self) -> str:
            return f"{self.project_id}.{self.log_level}"

    log_rabbit_message = InvalidLoggerRabbitMessage(
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        messages=100,
        log_level=logging.INFO,
    )
    with pytest.raises(ValidationError):
        LoggerRabbitMessage.model_validate(log_rabbit_message.model_dump())

    await produce_logs("expected", log_message=log_rabbit_message)

    ii: int = 0
    async for log in log_streamer_with_distributor.log_generator():
        _ = JobLog.model_validate_json(log)
        ii += 1
    assert ii == 0


class _MockLogDistributor:
    async def register(self, job_id: UUID, queue: asyncio.Queue):
        return None

    async def deregister(self, job_id: None):
        return None


async def test_log_generator(mocker: MockFixture, faker: Faker):
    mocker.patch(
        "simcore_service_api_server.services.log_streaming.LogStreamer._project_done",
        return_value=True,
    )
    log_streamer = LogStreamer(user_id=3, director2_api=None, job_id=None, log_distributor=_MockLogDistributor(), log_check_timeout=1)  # type: ignore

    published_logs: list[str] = []
    for _ in range(10):
        job_log = JobLog.model_validate(
            JobLog.model_config["json_schema_extra"]["example"]
        )
        msg = faker.text()
        published_logs.append(msg)
        job_log.messages = [msg]
        await log_streamer._queue.put(job_log)

    collected_logs: list[str] = []
    async for log in log_streamer.log_generator():
        job_log = JobLog.model_validate_json(log)
        assert len(job_log.messages) == 1
        collected_logs.append(job_log.messages[0])

    assert published_logs == collected_logs


@pytest.mark.parametrize("is_healthy", [True, False])
async def test_logstreaming_health_checker(
    mocker: MockFixture, client: httpx.AsyncClient, app: FastAPI, is_healthy: bool
):
    health_checker = get_health_checker(app)
    health_checker._timeout_seconds = 0.5
    health_checker._allowed_health_check_failures = 0
    put_method = health_checker._dummy_queue.put

    async def put_mock(log: JobLog):
        put_mock.called = True
        if is_healthy:
            await put_method(log)

    put_mock.called = False
    mocker.patch.object(health_checker._dummy_queue, "put", put_mock)
    health_setter = mocker.spy(health_checker, "_increment_health_check_failure_count")
    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_delay(5),
        retry=retry_if_not_exception_type(AssertionError),
    ):
        with attempt:
            await asyncio.sleep(1)
            assert put_mock.called
            if is_healthy:
                health_setter.assert_not_called()
            else:
                health_setter.assert_called()

    assert health_checker.healthy == is_healthy, "Health check failed"
