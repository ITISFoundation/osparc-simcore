# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import asyncio
import json
from random import choice
from typing import Any, Awaitable, Callable
from unittest import mock

import aiopg
import aiopg.sa
import pytest
import socketio
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.rabbitmq_messages import (
    EventRabbitMessage,
    InstrumentationRabbitMessage,
    LoggerRabbitMessage,
    ProgressRabbitMessageNode,
    ProgressType,
    RabbitEventMessageType,
)
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_login import UserInfoDict
from redis import Redis
from servicelib.aiohttp.application import create_safe_application
from servicelib.aiohttp.monitor_services import (
    MONITOR_SERVICE_STARTED_LABELS,
    MONITOR_SERVICE_STOPPED_LABELS,
)
from servicelib.rabbitmq import RabbitMQClient
from settings_library.rabbit import RabbitSettings
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.db.plugin import setup_db
from simcore_service_webserver.diagnostics.plugin import setup_diagnostics
from simcore_service_webserver.director_v2.plugin import setup_director_v2
from simcore_service_webserver.login.plugin import setup_login
from simcore_service_webserver.notifications import project_logs
from simcore_service_webserver.notifications.plugin import setup_notifications
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.projects.plugin import setup_projects
from simcore_service_webserver.resource_manager.plugin import setup_resource_manager
from simcore_service_webserver.rest.plugin import setup_rest
from simcore_service_webserver.security.plugin import setup_security
from simcore_service_webserver.session.plugin import setup_session
from simcore_service_webserver.socketio.messages import (
    SOCKET_IO_EVENT,
    SOCKET_IO_LOG_EVENT,
    SOCKET_IO_NODE_PROGRESS_EVENT,
    SOCKET_IO_NODE_UPDATED_EVENT,
)
from simcore_service_webserver.socketio.plugin import setup_socketio
from tenacity import RetryError
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_always, retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
    "redis",
]

pytest_simcore_ops_services_selection = []

_STABLE_DELAY_S = 2


async def _assert_handler_not_called(handler: mock.Mock) -> None:
    with pytest.raises(RetryError):
        async for attempt in AsyncRetrying(
            retry=retry_always,
            stop=stop_after_delay(_STABLE_DELAY_S),
            reraise=True,
            wait=wait_fixed(1),
        ):
            with attempt:
                print(
                    f"--> checking no message reached webclient for {attempt.retry_state.attempt_number}/{_STABLE_DELAY_S}s..."
                )
                handler.assert_not_called()
    print(f"no calls received for {_STABLE_DELAY_S}s. very good.")


async def _assert_handler_called(handler: mock.Mock, expected_call: mock._Call) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(10),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            print(
                f"--> checking if messages reached webclient... {attempt.retry_state.attempt_number} attempt"
            )
            handler.assert_has_calls([expected_call])
            print(f"calls received! {attempt.retry_state.retry_object.statistics}")


async def _assert_handler_called_with_json(
    handler: mock.Mock, expected_call: dict[str, Any] | list[dict[str, Any]]
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(10),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            print(
                f"--> checking if messages reached webclient... {attempt.retry_state.attempt_number} attempt"
            )
            handler.assert_called_once()
            call_args, _call_kwargs = handler.call_args
            assert json.loads(call_args[0]) == expected_call
            print(f"calls received! {attempt.retry_state.retry_object.statistics}")


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    app_config: dict[str, Any],
    rabbit_service: RabbitSettings,
    postgres_db: sa.engine.Engine,
    redis_client: Redis,
    monkeypatch_setenv_from_app_config: Callable,
) -> TestClient:
    app_config["storage"]["enabled"] = False

    monkeypatch_setenv_from_app_config(app_config)
    app = create_safe_application(app_config)

    assert setup_settings(app)

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_diagnostics(app)
    setup_login(app)
    setup_projects(app)
    setup_notifications(app)
    setup_director_v2(app)
    setup_socketio(app)
    setup_resource_manager(app)

    return event_loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={
                "port": app_config["main"]["port"],
                "host": app_config["main"]["host"],
            },
        )
    )


@pytest.fixture
async def rabbitmq_publisher(
    rabbitmq_client: Callable[[str], RabbitMQClient],
) -> RabbitMQClient:
    return rabbitmq_client("pytest_publisher")


@pytest.mark.parametrize("user_role", [UserRole.GUEST], ids=str)
@pytest.mark.parametrize(
    "sender_same_user_id", [True, False], ids=lambda id: f"same_sender_id={id}"
)
@pytest.mark.parametrize(
    "subscribe_to_logs", [True, False], ids=lambda id: f"subscribed={id}"
)
async def test_log_workflow(
    client: TestClient,
    rabbitmq_publisher: RabbitMQClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    faker: Faker,
    socketio_client_factory: Callable[
        [str | None, TestClient | None], Awaitable[socketio.AsyncClient]
    ],
    mocker: MockerFixture,
    sender_same_user_id: bool,
    subscribe_to_logs: bool,
):
    """
    RabbitMQ (TOPIC) --> Webserver --> Redis --> webclient (socketio)

    """
    socket_io_conn = await socketio_client_factory(None, client)

    mock_log_handler = mocker.MagicMock()
    socket_io_conn.on(SOCKET_IO_LOG_EVENT, handler=mock_log_handler)

    project_id = ProjectID(user_project["uuid"])
    random_node_id_in_project = NodeID(choice(list(user_project["workbench"])))
    sender_user_id = UserID(logged_user["id"])
    if sender_same_user_id is False:
        sender_user_id = UserID(faker.pyint(min_value=logged_user["id"] + 1))

    if subscribe_to_logs:
        assert client.app
        await project_logs.subscribe(client.app, project_id)

    log_message = LoggerRabbitMessage(
        user_id=sender_user_id,
        project_id=project_id,
        node_id=random_node_id_in_project,
        messages=[faker.text() for _ in range(10)],
    )
    await rabbitmq_publisher.publish(log_message.channel_name, log_message)

    call_expected = sender_same_user_id and subscribe_to_logs
    if call_expected:
        expected_call = jsonable_encoder(
            log_message, exclude={"user_id", "channel_name"}
        )
        await _assert_handler_called_with_json(mock_log_handler, expected_call)
    else:
        await _assert_handler_not_called(mock_log_handler)


@pytest.mark.parametrize("user_role", [UserRole.GUEST], ids=str)
async def test_log_workflow_only_receives_messages_if_subscribed(
    client: TestClient,
    rabbitmq_publisher: RabbitMQClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    faker: Faker,
    mocker: MockerFixture,
):
    """
    RabbitMQ (TOPIC) --> Webserver

    """
    mocked_send_messages = mocker.patch(
        "simcore_service_webserver.notifications._rabbitmq_consumers.send_messages",
        autospec=True,
    )

    project_id = ProjectID(user_project["uuid"])
    random_node_id_in_project = NodeID(choice(list(user_project["workbench"])))
    sender_user_id = UserID(logged_user["id"])

    assert client.app
    await project_logs.subscribe(client.app, project_id)

    log_message = LoggerRabbitMessage(
        user_id=sender_user_id,
        project_id=project_id,
        node_id=random_node_id_in_project,
        messages=[faker.text() for _ in range(10)],
    )
    await rabbitmq_publisher.publish(log_message.channel_name, log_message)
    await _assert_handler_called(
        mocked_send_messages,
        mock.call(
            client.app,
            log_message.user_id,
            [
                {
                    "event_type": SOCKET_IO_LOG_EVENT,
                    "data": log_message.dict(exclude={"user_id", "channel_name"}),
                }
            ],
        ),
    )
    mocked_send_messages.reset_mock()

    # when unsubscribed, we do not receive the messages anymore
    await project_logs.unsubscribe(client.app, project_id)
    await rabbitmq_publisher.publish(log_message.channel_name, log_message)
    await _assert_handler_not_called(mocked_send_messages)


@pytest.mark.parametrize("user_role", [UserRole.GUEST], ids=str)
@pytest.mark.parametrize(
    "progress_type",
    [p for p in ProgressType if p is not ProgressType.COMPUTATION_RUNNING],
    ids=str,
)
@pytest.mark.parametrize(
    "sender_same_user_id", [True, False], ids=lambda id: f"same_sender_id={id}"
)
@pytest.mark.parametrize(
    "subscribe_to_logs", [True, False], ids=lambda id: f"subscribed={id}"
)
async def test_progress_non_computational_workflow(
    client: TestClient,
    rabbitmq_publisher: RabbitMQClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    faker: Faker,
    socketio_client_factory: Callable[
        [str | None, TestClient | None], Awaitable[socketio.AsyncClient]
    ],
    mocker: MockerFixture,
    progress_type: ProgressType,
    sender_same_user_id: bool,
    subscribe_to_logs: bool,
):
    """
    RabbitMQ (TOPIC) --> Webserver -->  Redis --> webclient (socketio)

    """
    socket_io_conn = await socketio_client_factory(None, client)

    mock_progress_handler = mocker.MagicMock()
    socket_io_conn.on(SOCKET_IO_NODE_PROGRESS_EVENT, handler=mock_progress_handler)

    random_node_id_in_project = NodeID(choice(list(user_project["workbench"])))
    sender_user_id = UserID(logged_user["id"])
    project_id = ProjectID(user_project["uuid"])
    if sender_same_user_id is False:
        sender_user_id = UserID(faker.pyint(min_value=logged_user["id"] + 1))
    if subscribe_to_logs:
        assert client.app
        await project_logs.subscribe(client.app, project_id)
    progress_message = ProgressRabbitMessageNode(
        user_id=sender_user_id,
        project_id=ProjectID(user_project["uuid"]),
        node_id=random_node_id_in_project,
        progress=0.3,
        progress_type=progress_type,
    )
    await rabbitmq_publisher.publish(progress_message.channel_name, progress_message)

    call_expected = sender_same_user_id and subscribe_to_logs
    if call_expected:
        expected_call = jsonable_encoder(progress_message, exclude={"channel_name"})
        await _assert_handler_called_with_json(mock_progress_handler, expected_call)
    else:
        await _assert_handler_not_called(mock_progress_handler)


@pytest.mark.parametrize("user_role", [UserRole.GUEST], ids=str)
@pytest.mark.parametrize(
    "sender_same_user_id", [True, False], ids=lambda id: f"same_sender_id={id}"
)
@pytest.mark.parametrize(
    "subscribe_to_logs", [True, False], ids=lambda id: f"subscribed={id}"
)
async def test_progress_computational_workflow(
    client: TestClient,
    rabbitmq_publisher: RabbitMQClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    socketio_client_factory: Callable[
        [str | None, TestClient | None], Awaitable[socketio.AsyncClient]
    ],
    mocker: MockerFixture,
    aiopg_engine: aiopg.sa.Engine,
    sender_same_user_id: bool,
    faker: Faker,
    subscribe_to_logs: bool,
):
    """
    RabbitMQ (TOPIC) --> Webserver -->  DB (get project)
                                        Redis --> webclient (socketio)

    """
    socket_io_conn = await socketio_client_factory(None, client)

    mock_progress_handler = mocker.MagicMock()
    socket_io_conn.on(SOCKET_IO_NODE_UPDATED_EVENT, handler=mock_progress_handler)
    random_node_id_in_project = NodeID(choice(list(user_project["workbench"])))
    sender_user_id = UserID(logged_user["id"])
    project_id = ProjectID(user_project["uuid"])
    if sender_same_user_id is False:
        sender_user_id = UserID(faker.pyint(min_value=logged_user["id"] + 1))
    if subscribe_to_logs:
        assert client.app
        await project_logs.subscribe(client.app, project_id)
    progress_message = ProgressRabbitMessageNode(
        user_id=sender_user_id,
        project_id=ProjectID(user_project["uuid"]),
        node_id=random_node_id_in_project,
        progress=0.3,
        progress_type=ProgressType.COMPUTATION_RUNNING,
    )
    await rabbitmq_publisher.publish(progress_message.channel_name, progress_message)

    call_expected = sender_same_user_id and subscribe_to_logs
    if call_expected:
        expected_call = jsonable_encoder(
            progress_message, include={"node_id", "project_id"}
        )
        expected_call |= {
            "data": user_project["workbench"][f"{random_node_id_in_project}"]
        }
        expected_call["data"]["progress"] = int(progress_message.progress * 100)
        await _assert_handler_called_with_json(mock_progress_handler, expected_call)
    else:
        await _assert_handler_not_called(mock_progress_handler)

    # check the database. doing it after the waiting calls above is safe
    async with aiopg_engine.acquire() as conn:
        result = await conn.execute(
            sa.select(projects.c.workbench).where(
                projects.c.uuid == user_project["uuid"]
            )
        )
        row = await result.fetchone()
        assert row
        project_workbench = dict(row[projects.c.workbench])
        # NOTE: the progress might still be present but is not used anymore
        assert project_workbench[f"{random_node_id_in_project}"].get("progress", 0) == 0


@pytest.mark.parametrize("user_role", [UserRole.GUEST], ids=str)
@pytest.mark.parametrize("metrics_name", ["service_started", "service_stopped"])
async def test_instrumentation_workflow(
    client: TestClient,
    rabbitmq_publisher: RabbitMQClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    mocker: MockerFixture,
    faker: Faker,
    metrics_name: str,
):
    """
    RabbitMQ --> Webserver -->  Prometheus metrics

    """

    mocked_metrics_method = mocker.patch(
        f"simcore_service_webserver.notifications._rabbitmq_consumers.{metrics_name}"
    )

    random_node_id_in_project = NodeID(choice(list(user_project["workbench"])))
    rabbit_message = InstrumentationRabbitMessage(
        user_id=UserID(logged_user["id"]),
        project_id=ProjectID(user_project["uuid"]),
        node_id=random_node_id_in_project,
        metrics=metrics_name,
        service_uuid=faker.uuid4(),
        service_key=faker.pystr(),
        service_tag=faker.pystr(),
        result=RunningState.STARTED,
        simcore_user_agent=faker.pystr(),
        service_type=faker.pystr(),
    )
    await rabbitmq_publisher.publish(rabbit_message.channel_name, rabbit_message)

    included_labels = MONITOR_SERVICE_STARTED_LABELS
    if metrics_name == "service_stopped":
        included_labels = MONITOR_SERVICE_STOPPED_LABELS
    await _assert_handler_called(
        mocked_metrics_method,
        mock.call(
            client.app,
            **rabbit_message.dict(include=set(included_labels)),
        ),
    )


@pytest.mark.parametrize("user_role", [UserRole.GUEST], ids=str)
@pytest.mark.parametrize(
    "sender_same_user_id", [True, False], ids=lambda id: f"same_sender_id={id}"
)
async def test_event_workflow(
    client: TestClient,
    rabbitmq_publisher: RabbitMQClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    socketio_client_factory: Callable[
        [str | None, TestClient | None], Awaitable[socketio.AsyncClient]
    ],
    mocker: MockerFixture,
    sender_same_user_id: bool,
    faker: Faker,
):
    """
    RabbitMQ --> Webserver --> Redis --> webclient (socketio)

    """
    socket_io_conn = await socketio_client_factory(None, client)
    mock_event_handler = mocker.MagicMock()
    socket_io_conn.on(SOCKET_IO_EVENT, handler=mock_event_handler)

    sender_user_id = UserID(logged_user["id"])
    if sender_same_user_id is False:
        sender_user_id = UserID(faker.pyint(min_value=logged_user["id"] + 1))
    random_node_id_in_project = NodeID(choice(list(user_project["workbench"])))
    rabbit_message = EventRabbitMessage(
        user_id=sender_user_id,
        project_id=ProjectID(user_project["uuid"]),
        node_id=random_node_id_in_project,
        action=RabbitEventMessageType.RELOAD_IFRAME,
    )

    await rabbitmq_publisher.publish(rabbit_message.channel_name, rabbit_message)

    call_expected = sender_same_user_id
    if call_expected:
        expected_call = jsonable_encoder(rabbit_message, include={"action", "node_id"})
        await _assert_handler_called_with_json(mock_event_handler, expected_call)
    else:
        await _assert_handler_not_called(mock_event_handler)
