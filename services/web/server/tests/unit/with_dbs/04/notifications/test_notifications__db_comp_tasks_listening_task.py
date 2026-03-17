# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=too-many-arguments
# pylint:disable=protected-access

import asyncio
import json
import logging
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
import simcore_service_webserver
import simcore_service_webserver.db_listener
import simcore_service_webserver.db_listener._db_comp_tasks_listening_task
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses as AioResponsesMock
from common_library.async_tools import delayed_start
from faker import Faker
from models_library.projects import ProjectAtDB
from models_library.projects_nodes import InputsDict
from models_library.projects_nodes_io import NodeID
from pytest_mock import MockType
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_tasks import NodeClass, comp_tasks
from simcore_postgres_database.models.users import UserRole
from simcore_postgres_database.webserver_models import DB_CHANNEL_NAME
from simcore_service_webserver.db_listener._db_comp_tasks_listening_task import (
    _get_changed_comp_task_row,
    _get_project_owner,
    _handle_db_notification,
    create_comp_tasks_listening_task,
)
from simcore_service_webserver.db_listener._models import CompTaskNotificationPayload
from simcore_service_webserver.projects import exceptions
from sqlalchemy.ext.asyncio import AsyncEngine
from tenacity import stop_after_attempt
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

logger = logging.getLogger(__name__)


@pytest.fixture
async def mock_project_subsystem(mocker: MockerFixture) -> dict[str, mock.Mock]:
    mocked_project_calls = {}

    mocked_project_calls["update_node_outputs"] = mocker.patch(
        "simcore_service_webserver.db_listener._db_comp_tasks_listening_task.update_node_outputs",
        return_value="",
    )

    mocked_project_calls["_update_project_state.update_project_node_state"] = mocker.patch(
        "simcore_service_webserver.projects._projects_service.update_project_node_state",
        autospec=True,
    )

    mocked_project_calls["_update_project_state.notify_project_node_update"] = mocker.patch(
        "simcore_service_webserver.projects._projects_service.notify_project_node_update",
        autospec=True,
    )

    mocked_project_calls["_update_project_state.notify_project_state_update"] = mocker.patch(
        "simcore_service_webserver.projects._projects_service.notify_project_state_update",
        autospec=True,
    )

    return mocked_project_calls


@pytest.fixture
async def with_started_listening_task(client: TestClient) -> AsyncIterator:
    assert client.app
    async for _comp_task in create_comp_tasks_listening_task(client.app):
        # first call creates the task, second call cleans it
        yield


@pytest.fixture
async def spied_get_changed_comp_task_row(
    mocker: MockerFixture,
) -> MockType:
    return mocker.spy(
        simcore_service_webserver.db_listener._db_comp_tasks_listening_task,  # noqa: SLF001
        "_get_changed_comp_task_row",
    )


@dataclass(frozen=True, slots=True)
class _CompTaskChangeParams:
    update_values: dict[str, Any]
    expected_calls: list[str]


async def _assert_listener_triggers(mock_project_subsystem: dict[str, mock.Mock], expected_calls: list[str]) -> None:
    for call_name, mocked_call in mock_project_subsystem.items():
        if call_name in expected_calls:
            async for attempt in AsyncRetrying(
                wait=wait_fixed(1),
                stop=stop_after_delay(10),
                retry=retry_if_exception_type(AssertionError),
                before_sleep=before_sleep_log(logger, logging.INFO),
                reraise=True,
            ):
                with attempt:
                    mocked_call.assert_called_once()

        else:
            mocked_call.assert_not_called()


@pytest.mark.parametrize("task_class", [NodeClass.COMPUTATIONAL, NodeClass.INTERACTIVE, NodeClass.FRONTEND])
@pytest.mark.parametrize(
    "params",
    [
        pytest.param(
            _CompTaskChangeParams(
                {
                    "outputs": {"some new stuff": "it is new"},
                },
                ["update_node_outputs"],
            ),
            id="new output shall trigger",
        ),
        pytest.param(
            _CompTaskChangeParams(
                {"state": StateType.ABORTED},
                [
                    "_update_project_state.update_project_node_state",
                    "_update_project_state.notify_project_node_update",
                    "_update_project_state.notify_project_state_update",
                ],
            ),
            id="new state shall trigger",
        ),
        pytest.param(
            _CompTaskChangeParams(
                {
                    "outputs": {"some new stuff": "it is new"},
                    "state": StateType.ABORTED,
                },
                [
                    "update_node_outputs",
                    "_update_project_state.update_project_node_state",
                    "_update_project_state.notify_project_node_update",
                    "_update_project_state.notify_project_state_update",
                ],
            ),
            id="new output and state shall double trigger",
        ),
        pytest.param(
            _CompTaskChangeParams({"inputs": {"should not trigger": "right?"}}, []),
            id="no new output or state shall not trigger",
        ),
    ],
)
@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_db_listener_triggers_on_event_with_multiple_tasks(
    sqlalchemy_async_engine: AsyncEngine,
    mock_project_subsystem: dict[str, mock.Mock],
    spied_get_changed_comp_task_row: MockType,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    with_started_listening_task: None,
    params: _CompTaskChangeParams,
    task_class: NodeClass,
    faker: Faker,
    mocker: MockerFixture,
):
    some_project = await create_project(logged_user)
    await create_pipeline(project_id=f"{some_project.uuid}")
    # Create 3 tasks with different node_ids
    tasks = [
        await create_comp_task(
            project_id=f"{some_project.uuid}",
            node_id=faker.uuid4(),
            outputs=json.dumps({}),
            node_class=task_class,
        )
        for _ in range(3)
    ]
    random_task_to_update = tasks[secrets.randbelow(len(tasks))]
    updated_task_id = random_task_to_update["task_id"]

    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(**params.update_values).where(comp_tasks.c.task_id == updated_task_id)
        )
    await _assert_listener_triggers(mock_project_subsystem, params.expected_calls)

    # Assert the spy was called with the correct task_id
    if params.expected_calls:
        assert any(call.args[1] == updated_task_id for call in spied_get_changed_comp_task_row.call_args_list), (
            f"_get_changed_comp_task_row was not called with task_id={updated_task_id}. Calls: {spied_get_changed_comp_task_row.call_args_list}"
        )
    else:
        spied_get_changed_comp_task_row.assert_not_called()


@pytest.fixture
def fake_2connected_jupyterlabs_workbench(tests_data_dir: Path) -> dict[str, Any]:
    fpath = tests_data_dir / "workbench_2connected_jupyterlabs.json"
    assert fpath.exists()
    return json.loads(fpath.read_text())


@pytest.fixture
async def mock_dynamic_service_rpc(
    mocker: MockerFixture,
) -> mock.AsyncMock:
    """
    Mocks the dynamic service RPC calls to avoid actual service calls during tests.
    """
    import servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.services

    return mocker.patch.object(
        servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.services,
        "retrieve_inputs",
        autospec=True,
    )


async def _check_for_stability(function: Callable[..., Awaitable[None]], *args, **kwargs) -> None:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(5),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(),
        reraise=True,
    ):
        with attempt:  # noqa: SIM117
            with log_context(
                logging.INFO,
                msg=f"check stability of {function.__name__} {attempt.retry_state.retry_object.statistics}",
            ) as log_ctx:
                await function(*args, **kwargs)
                log_ctx.logger.info("stable for %s...", attempt.retry_state.seconds_since_start)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_db_listener_upgrades_projects_row_correctly(
    with_started_listening_task: None,
    director_v2_service_mock: AioResponsesMock,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    mock_dynamic_service_rpc: mock.AsyncMock,
    sqlalchemy_async_engine: AsyncEngine,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    fake_2connected_jupyterlabs_workbench: dict[str, Any],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    spied_get_changed_comp_task_row: MockType,
    faker: Faker,
):
    some_project = await create_project(logged_user, workbench=fake_2connected_jupyterlabs_workbench)

    # create the corresponding comp_task entries for the project workbench
    await create_pipeline(project_id=f"{some_project.uuid}")
    tasks = [
        await create_comp_task(
            project_id=f"{some_project.uuid}",
            node_id=node_id,
            outputs=node_data.get("outputs", {}),
            node_class=(NodeClass.INTERACTIVE if "dynamic" in node_data["key"] else NodeClass.COMPUTATIONAL),
            inputs=node_data.get("inputs", InputsDict()),
        )
        for node_id, node_data in fake_2connected_jupyterlabs_workbench.items()
    ]
    assert len(tasks) == 2, "Expected two tasks for the two JupyterLab nodes"
    first_jupyter_task = tasks[0]
    second_jupyter_task = tasks[1]
    assert len(second_jupyter_task["inputs"]) > 0, "Expected inputs for the second JupyterLab task"
    number_of_inputs_linked = len(second_jupyter_task["inputs"])

    # simulate a concurrent change in all the outputs of first jupyterlab
    async def _update_first_jupyter_task_output(port_index: int, data: dict[str, Any]) -> None:
        with log_context(logging.INFO, msg=f"Updating output {port_index + 1}"):
            async with sqlalchemy_async_engine.begin() as conn:
                result = await conn.execute(
                    comp_tasks.select()
                    .with_only_columns(comp_tasks.c.outputs)
                    .where(comp_tasks.c.task_id == first_jupyter_task["task_id"])
                    .with_for_update()
                )
                row = result.first()
                current_outputs = row[0] if row and row[0] else {}

                # Update/add the new key while preserving existing keys
                current_outputs[f"output_{port_index + 1}"] = data

                # Write back the updated outputs
                await conn.execute(
                    comp_tasks.update()
                    .values(outputs=current_outputs)
                    .where(comp_tasks.c.task_id == first_jupyter_task["task_id"])
                )

    @delayed_start(timedelta(seconds=2))
    async def _change_outputs_sequentially(sleep: float) -> None:
        """
        Sequentially updates the outputs of the second JupyterLab task to trigger the dynamic service RPC.
        """
        for i in range(number_of_inputs_linked):
            await _update_first_jupyter_task_output(i, {"data": i})
            await asyncio.sleep(sleep)

    # this runs in a task
    sequential_task = asyncio.create_task(_change_outputs_sequentially(5))
    assert sequential_task is not None, "Failed to create the sequential task"

    async def _check_retrieve_rpc_called(expected_ports_retrieved: int) -> None:
        async for attempt in AsyncRetrying(
            stop=stop_after_delay(60),
            wait=wait_fixed(1),
            retry=retry_if_exception_type(AssertionError),
            reraise=True,
        ):
            with attempt:  # noqa: SIM117
                with log_context(
                    logging.INFO,
                    msg=f"Checking if dynamic service retrieve RPC was called and "
                    f"all expected ports were retrieved {expected_ports_retrieved} "
                    f"times,  {attempt.retry_state.retry_object.statistics}",
                ) as log_ctx:
                    if mock_dynamic_service_rpc.call_count > 0:
                        log_ctx.logger.info(
                            "call arguments: %s",
                            mock_dynamic_service_rpc.call_args_list,
                        )
                    # Assert that the dynamic service RPC was called
                    assert mock_dynamic_service_rpc.call_count > 0, "Dynamic service retrieve RPC was not called"
                    # now get we check which ports were retrieved, we expect all of them
                    all_ports = set()
                    for call in mock_dynamic_service_rpc.call_args_list:
                        retrieved_ports = call[1]["port_keys"]
                        all_ports.update(retrieved_ports)
                    assert len(all_ports) == expected_ports_retrieved, (
                        f"Expected {expected_ports_retrieved} ports to be retrieved, "
                        f"but got {len(all_ports)}: {all_ports}"
                    )
                    log_ctx.logger.info("Dynamic service retrieve RPC was called with all expected ports!")

    await _check_for_stability(_check_retrieve_rpc_called, number_of_inputs_linked)
    await asyncio.wait_for(sequential_task, timeout=60)
    assert sequential_task.done(), "Sequential task did not complete"
    assert not sequential_task.cancelled(), "Sequential task was cancelled unexpectedly"


# --------- Unit tests for db_listener internal functions ---------


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_get_project_owner_returns_valid_owner(
    sqlalchemy_async_engine: AsyncEngine,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
):
    project = await create_project(logged_user)
    async with sqlalchemy_async_engine.connect() as conn:
        owner = await _get_project_owner(conn, project.uuid)
    assert owner == logged_user["id"]


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_get_project_owner_raises_when_project_missing(
    sqlalchemy_async_engine: AsyncEngine,
    logged_user: UserInfoDict,
    faker: Faker,
):
    missing_uuid = faker.uuid4()
    async with sqlalchemy_async_engine.connect() as conn:
        with pytest.raises(exceptions.ProjectOwnerNotFoundError):
            await _get_project_owner(conn, missing_uuid)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_get_changed_comp_task_row_returns_task(
    sqlalchemy_async_engine: AsyncEngine,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=faker.uuid4(),
        outputs=json.dumps({}),
        node_class=NodeClass.COMPUTATIONAL,
    )
    async with sqlalchemy_async_engine.connect() as conn:
        row = await _get_changed_comp_task_row(conn, task["task_id"])
    assert row is not None
    assert row.task_id == task["task_id"]


async def test_get_changed_comp_task_row_returns_none_for_missing_task(
    sqlalchemy_async_engine: AsyncEngine,
):
    async with sqlalchemy_async_engine.connect() as conn:
        row = await _get_changed_comp_task_row(conn, 999999)
    assert row is None


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_handle_db_notification_logs_warning_on_missing_project(
    sqlalchemy_async_engine: AsyncEngine,
    client: TestClient,
    logged_user: UserInfoDict,
    faker: Faker,
    caplog: pytest.LogCaptureFixture,
):
    assert client.app
    payload = CompTaskNotificationPayload(
        action="UPDATE",
        changes=["outputs"],
        table="comp_tasks",
        task_id=999999,
        project_id=faker.uuid4(),
        node_id=faker.uuid4(),
    )
    with caplog.at_level(logging.WARNING):
        await _handle_db_notification(client.app, payload, sqlalchemy_async_engine)
    assert "could not be found" in caplog.text or "not found" in caplog.text.lower()


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_handle_db_notification_logs_warning_on_missing_comp_task(
    sqlalchemy_async_engine: AsyncEngine,
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    caplog: pytest.LogCaptureFixture,
    faker: Faker,
):
    assert client.app
    project = await create_project(logged_user)
    payload = CompTaskNotificationPayload(
        action="UPDATE",
        changes=["outputs"],
        table="comp_tasks",
        task_id=999999,
        project_id=project.uuid,
        node_id=faker.uuid4(),
    )
    with caplog.at_level(logging.WARNING):
        await _handle_db_notification(client.app, payload, sqlalchemy_async_engine)
    assert "No comp_tasks row found" in caplog.text


@pytest.mark.parametrize("task_class", [NodeClass.COMPUTATIONAL])
@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_handle_db_notification_with_output_change(
    sqlalchemy_async_engine: AsyncEngine,
    mock_project_subsystem: dict[str, mock.Mock],
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    task_class: NodeClass,
    faker: Faker,
):
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    node_id = faker.uuid4()
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=node_id,
        outputs=json.dumps({"out1": "val1"}),
        node_class=task_class,
    )
    payload = CompTaskNotificationPayload(
        action="UPDATE",
        changes=["outputs"],
        table="comp_tasks",
        task_id=task["task_id"],
        project_id=project.uuid,
        node_id=node_id,
    )
    await _handle_db_notification(client.app, payload, sqlalchemy_async_engine)
    mock_project_subsystem["update_node_outputs"].assert_called_once()


@pytest.mark.parametrize("task_class", [NodeClass.COMPUTATIONAL])
@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_handle_db_notification_with_state_change(
    sqlalchemy_async_engine: AsyncEngine,
    mock_project_subsystem: dict[str, mock.Mock],
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    task_class: NodeClass,
    faker: Faker,
):
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    node_id = faker.uuid4()
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=node_id,
        outputs=json.dumps({}),
        node_class=task_class,
    )
    # Update the task state in DB
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(state=StateType.ABORTED).where(comp_tasks.c.task_id == task["task_id"])
        )
    payload = CompTaskNotificationPayload(
        action="UPDATE",
        changes=["state"],
        table="comp_tasks",
        task_id=task["task_id"],
        project_id=project.uuid,
        node_id=node_id,
    )
    await _handle_db_notification(client.app, payload, sqlalchemy_async_engine)
    mock_project_subsystem["_update_project_state.update_project_node_state"].assert_called_once()
    mock_project_subsystem["_update_project_state.notify_project_node_update"].assert_called_once()
    mock_project_subsystem["_update_project_state.notify_project_state_update"].assert_called_once()


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_handle_db_notification_ignores_non_output_non_state_changes(
    sqlalchemy_async_engine: AsyncEngine,
    mock_project_subsystem: dict[str, mock.Mock],
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    node_id = faker.uuid4()
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=node_id,
        outputs=json.dumps({}),
        node_class=NodeClass.COMPUTATIONAL,
    )
    payload = CompTaskNotificationPayload(
        action="UPDATE",
        changes=["inputs"],
        table="comp_tasks",
        task_id=task["task_id"],
        project_id=project.uuid,
        node_id=node_id,
    )
    await _handle_db_notification(client.app, payload, sqlalchemy_async_engine)
    for mocked_call in mock_project_subsystem.values():
        mocked_call.assert_not_called()


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_listen_notify_asyncpg_receives_notifications(
    sqlalchemy_async_engine: AsyncEngine,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    """Tests that asyncpg LISTEN/NOTIFY callback receives notifications
    when comp_tasks rows are updated (trigger fires NOTIFY)."""
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    node_id = faker.uuid4()
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=node_id,
        outputs=json.dumps({}),
        node_class=NodeClass.COMPUTATIONAL,
    )

    received: asyncio.Queue[str] = asyncio.Queue()

    def _on_notification(conn: object, pid: int, channel: str, payload: str) -> None:
        received.put_nowait(payload)

    # Set up a raw asyncpg listener
    async with sqlalchemy_async_engine.connect() as conn:
        raw_conn = await conn.get_raw_connection()
        asyncpg_conn = raw_conn.driver_connection
        await asyncpg_conn.add_listener(DB_CHANNEL_NAME, _on_notification)

        try:
            # Trigger an UPDATE that should fire the NOTIFY
            async with sqlalchemy_async_engine.begin() as write_conn:
                await write_conn.execute(
                    comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
                )

            # Wait for the notification
            raw_payload = await asyncio.wait_for(received.get(), timeout=5.0)
            parsed = CompTaskNotificationPayload.model_validate_json(raw_payload)
            assert parsed.task_id == task["task_id"]
            assert parsed.project_id == project.uuid
            assert parsed.node_id == NodeID(node_id)
            assert "outputs" in parsed.changes
        finally:
            await asyncpg_conn.remove_listener(DB_CHANNEL_NAME, _on_notification)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_listen_notify_asyncpg_multiple_rapid_updates(
    sqlalchemy_async_engine: AsyncEngine,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    """Tests that multiple rapid updates each produce a notification."""
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    node_id = faker.uuid4()
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=node_id,
        outputs=json.dumps({}),
        node_class=NodeClass.COMPUTATIONAL,
    )

    received: asyncio.Queue[str] = asyncio.Queue()

    def _on_notification(conn: object, pid: int, channel: str, payload: str) -> None:
        received.put_nowait(payload)

    async with sqlalchemy_async_engine.connect() as conn:
        raw_conn = await conn.get_raw_connection()
        asyncpg_conn = raw_conn.driver_connection
        await asyncpg_conn.add_listener(DB_CHANNEL_NAME, _on_notification)

        try:
            num_updates = 5
            for i in range(num_updates):
                async with sqlalchemy_async_engine.begin() as write_conn:
                    await write_conn.execute(
                        comp_tasks.update()
                        .values(outputs={f"output_{i}": f"data_{i}"})
                        .where(comp_tasks.c.task_id == task["task_id"])
                    )

            # Collect all notifications
            notifications = []
            for _ in range(num_updates):
                raw_payload = await asyncio.wait_for(received.get(), timeout=5.0)
                notifications.append(CompTaskNotificationPayload.model_validate_json(raw_payload))

            assert len(notifications) == num_updates
            for n in notifications:
                assert n.task_id == task["task_id"]
                assert "outputs" in n.changes
        finally:
            await asyncpg_conn.remove_listener(DB_CHANNEL_NAME, _on_notification)
