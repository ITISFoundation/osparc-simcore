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
import simcore_service_webserver.db_listener._service
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses as AioResponsesMock  # noqa: N812
from common_library.async_tools import delayed_start
from faker import Faker
from models_library.projects import ProjectAtDB
from pytest_mock import MockType
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_tasks import NodeClass, comp_tasks
from simcore_postgres_database.models.outbox_events import outbox_events
from simcore_postgres_database.models.users import UserRole
from simcore_postgres_database.webserver_models import DB_OUTBOX_KIND_COMP_TASK_SYNC
from simcore_service_webserver.db_listener._repository import (
    EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER,
    get_comp_task,
    get_project_owner,
)
from simcore_service_webserver.db_listener._service import (
    _claim_and_process_one_outbox_event,
    _process_outbox_event,
    claim_and_process_outbox_events,
)
from simcore_service_webserver.db_listener.errors import CompTaskNotFoundError
from simcore_service_webserver.db_listener.models import (
    ClaimOutcome,
)
from simcore_service_webserver.db_listener.plugin import (
    create_comp_tasks_listening_task,
)
from simcore_service_webserver.projects import exceptions
from sqlalchemy.ext.asyncio import AsyncEngine
from tenacity import stop_after_attempt
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

logger = logging.getLogger(__name__)

_COUNT_LISTENER_CONNECTIONS_SQL = (
    "select count(*) from pg_stat_activity where application_name like :pattern and pid != pg_backend_pid()"
)


@pytest.fixture
async def mock_project_subsystem(mocker: MockerFixture) -> dict[str, mock.Mock]:
    mocked_project_calls = {}

    mocked_project_calls["update_node_outputs"] = mocker.patch(
        "simcore_service_webserver.db_listener._service.update_node_outputs",
        return_value="",
    )

    mocked_project_calls["_update_project_state.update_project_node_state"] = mocker.patch(
        "simcore_service_webserver.db_listener._service.update_project_node_state",
        autospec=True,
    )

    mocked_project_calls["_update_project_state.notify_project_node_update"] = mocker.patch(
        "simcore_service_webserver.db_listener._service.notify_project_node_update",
        autospec=True,
    )

    mocked_project_calls["_update_project_state.notify_project_state_update"] = mocker.patch(
        "simcore_service_webserver.db_listener._service.notify_project_state_update",
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
async def spied_get_comp_task(
    mocker: MockerFixture,
) -> MockType:
    return mocker.spy(
        simcore_service_webserver.db_listener._service,  # noqa: SLF001
        "get_comp_task",
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
    spied_get_comp_task: MockType,
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
            outputs={},
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
        assert any(call.args[1] == updated_task_id for call in spied_get_comp_task.call_args_list), (
            f"get_comp_task was not called with task_id={updated_task_id}. Calls: {spied_get_comp_task.call_args_list}"
        )
    else:
        spied_get_comp_task.assert_not_called()


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
    import servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.services  # noqa: PLC0415

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
    spied_get_comp_task: MockType,
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
            inputs=node_data.get("inputs", {}),
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
        owner = await get_project_owner(conn, project.uuid)
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
            await get_project_owner(conn, missing_uuid)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_get_comp_task_returns_task(
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
        outputs={},
        node_class=NodeClass.COMPUTATIONAL,
    )
    async with sqlalchemy_async_engine.connect() as conn:
        row = await get_comp_task(conn, task["task_id"])
    assert row.task_id == task["task_id"]


async def test_get_comp_task_raises_for_missing_task(
    sqlalchemy_async_engine: AsyncEngine,
):
    async with sqlalchemy_async_engine.connect() as conn:
        with pytest.raises(CompTaskNotFoundError):
            await get_comp_task(conn, 999999)


# --------- Unit tests for outbox claim/process functions ---------


async def _get_outbox_events_for_task(engine: AsyncEngine, task_id: int) -> list[dict]:
    async with engine.connect() as conn:
        result = await conn.execute(outbox_events.select().where(outbox_events.c.aggregate_id == f"{task_id}"))
        return [dict(r) for r in result.mappings().all()]


@pytest.fixture(autouse=True)
async def purge_outbox_events(
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[Callable[[], Awaitable[None]]]:
    """Empties the outbox queue before and after every test.

    Claims are global (any worker claims the oldest pending event), so events
    left over from a previous test (e.g. by the retry/dead-letter tests, whose
    comp_tasks rows get cascade-deleted) would otherwise leak into the next one.
    The finalizer purges automatically; a test may also call the returned
    callable to purge in the middle of a test.
    """

    async def _purge() -> None:
        async with sqlalchemy_async_engine.begin() as conn:
            await conn.execute(outbox_events.delete())

    await _purge()
    yield _purge
    await _purge()


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_process_outbox_event_logs_warning_on_missing_comp_task(
    sqlalchemy_async_engine: AsyncEngine,
    client: TestClient,
    logged_user: UserInfoDict,
    caplog: pytest.LogCaptureFixture,
):
    assert client.app
    with caplog.at_level(logging.WARNING):
        async with sqlalchemy_async_engine.connect() as conn:
            await _process_outbox_event(client.app, conn, 999999, frozenset({"outputs"}))
    assert "not found" in caplog.text.lower()


@pytest.mark.parametrize("task_class", [NodeClass.COMPUTATIONAL])
@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_process_outbox_event_with_output_change(
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
        outputs={"out1": "val1"},
        node_class=task_class,
    )
    async with sqlalchemy_async_engine.connect() as conn:
        await _process_outbox_event(client.app, conn, task["task_id"], frozenset({"outputs"}))
    mock_project_subsystem["update_node_outputs"].assert_called_once()


@pytest.mark.parametrize("task_class", [NodeClass.COMPUTATIONAL])
@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_process_outbox_event_with_run_hash_change(
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
        outputs={"out1": "val1"},
        node_class=task_class,
    )
    new_run_hash = faker.sha256()
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(run_hash=new_run_hash).where(comp_tasks.c.task_id == task["task_id"])
        )
    async with sqlalchemy_async_engine.connect() as conn:
        await _process_outbox_event(client.app, conn, task["task_id"], frozenset({"run_hash"}))
    # a run_hash-only change must still project outputs+run_hash onto the node
    mock_project_subsystem["update_node_outputs"].assert_called_once()
    # (app, user_id, project_id, node_id, outputs, run_hash, ...)
    assert mock_project_subsystem["update_node_outputs"].call_args.args[5] == new_run_hash


@pytest.mark.parametrize("task_class", [NodeClass.COMPUTATIONAL])
@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_process_outbox_event_with_state_change(
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
        outputs={},
        node_class=task_class,
    )
    # Update the task state in DB
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(state=StateType.ABORTED).where(comp_tasks.c.task_id == task["task_id"])
        )
    async with sqlalchemy_async_engine.connect() as conn:
        await _process_outbox_event(client.app, conn, task["task_id"], frozenset({"state"}))
    mock_project_subsystem["_update_project_state.update_project_node_state"].assert_called_once()
    mock_project_subsystem["_update_project_state.notify_project_node_update"].assert_called_once()
    mock_project_subsystem["_update_project_state.notify_project_state_update"].assert_called_once()
    # the outbox path must notify strictly, so a failed emit keeps the event for a retry
    assert mock_project_subsystem["_update_project_state.notify_project_node_update"].await_args.kwargs["strict"]
    assert mock_project_subsystem["_update_project_state.notify_project_state_update"].await_args.kwargs["strict"]


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_claim_and_process_one_deletes_event_on_success(
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
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=faker.uuid4(),
        outputs={},
        node_class=NodeClass.COMPUTATIONAL,
    )
    # the comp_tasks trigger only fires on outputs/state/run_hash updates, so we generate one
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
        )

    rows_before = await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"])
    assert len(rows_before) == 1

    # an event was claimed, processed, and deleted
    outcome = await _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set())
    assert outcome is not None
    assert isinstance(outcome, ClaimOutcome)
    assert outcome.success is True
    assert outcome.kind == DB_OUTBOX_KIND_COMP_TASK_SYNC
    assert outcome.aggregate_id == f"{task['task_id']}"

    # the row must have been removed on success
    rows_after = await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"])
    assert rows_after == []

    # no more events pending
    assert await _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set()) is None


async def test_claim_and_process_one_returns_none_when_empty(
    sqlalchemy_async_engine: AsyncEngine,
    client: TestClient,
):
    assert client.app
    assert await _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set()) is None


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_failed_processing_keeps_event_for_retry(
    sqlalchemy_async_engine: AsyncEngine,
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    mocker: MockerFixture,
    faker: Faker,
):
    """At-least-once delivery: a failure rolls back the claim, keeps the row,
    and records the attempt (crash-safety: the event is never lost)."""
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=faker.uuid4(),
        outputs={},
        node_class=NodeClass.COMPUTATIONAL,
    )
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
        )

    mocker.patch(
        "simcore_service_webserver.db_listener._service._process_outbox_event",
        side_effect=RuntimeError("boom"),
    )

    # processing fails: the event must remain claimable with the attempt recorded
    outcome = await _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set())
    assert outcome is not None
    assert outcome.success is False

    rows = await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"])
    assert len(rows) == 1, "failed event must NOT be deleted"
    assert rows[0]["attempts"] == 1
    assert "boom" in rows[0]["last_error"]

    # inside the retry backoff window the event is not claimable again
    assert await _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set()) is None

    # once the backoff window passed, a second attempt bumps attempts again
    # (row updated in place, not re-inserted)
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(outbox_events.update().values(next_attempt_at=sa.text("now() - interval '1 hour'")))
    outcome = await _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set())
    assert outcome is not None
    assert outcome.success is False
    rows = await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"])
    assert len(rows) == 1
    assert rows[0]["attempts"] == 2


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_dead_lettered_events_are_skipped_by_claims(
    sqlalchemy_async_engine: AsyncEngine,
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
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=faker.uuid4(),
        outputs={},
        node_class=NodeClass.COMPUTATIONAL,
    )
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
        )
        # simulate an event that exhausted its retries
        await conn.execute(outbox_events.update().values(attempts=EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER))

    # claims skip dead-lettered events: nothing is claimable
    assert await _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set()) is None

    # the dead-lettered row is kept for post-mortem
    rows = await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"])
    assert len(rows) == 1
    assert rows[0]["attempts"] == EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_claim_and_process_outbox_events_drains_all_pending_events(
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
    tasks = [
        await create_comp_task(
            project_id=f"{project.uuid}",
            node_id=faker.uuid4(),
            outputs={},
            node_class=NodeClass.COMPUTATIONAL,
        )
        for _ in range(3)
    ]
    async with sqlalchemy_async_engine.begin() as conn:
        for task in tasks:
            await conn.execute(
                comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
            )

    async with sqlalchemy_async_engine.connect() as conn:
        result = await conn.execute(outbox_events.select())
        assert len(result.fetchall()) == 3

    await claim_and_process_outbox_events(client.app, sqlalchemy_async_engine)

    assert mock_project_subsystem["update_node_outputs"].call_count == 3
    async with sqlalchemy_async_engine.connect() as conn:
        result = await conn.execute(outbox_events.select())
        assert result.fetchall() == []


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_drain_coalesces_all_events_of_the_same_aggregate(
    sqlalchemy_async_engine: AsyncEngine,
    mock_project_subsystem: dict[str, mock.Mock],
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    """A burst of events for one aggregate must fan out a *single* notification:
    all pending events of the claimed aggregate are coalesced into one projection
    (union of their changed_columns) and deleted together."""
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=faker.uuid4(),
        outputs={},
        node_class=NodeClass.COMPUTATIONAL,
    )
    # 10 distinct outputs updates -> 10 outbox events for the same aggregate
    for i in range(10):
        async with sqlalchemy_async_engine.begin() as conn:
            await conn.execute(
                comp_tasks.update().values(outputs={f"update-{i}": i}).where(comp_tasks.c.task_id == task["task_id"])
            )

    rows_before = await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"])
    assert len(rows_before) == 10

    await claim_and_process_outbox_events(client.app, sqlalchemy_async_engine)

    # one projection for all coalesced events, not one per event
    mock_project_subsystem["update_node_outputs"].assert_called_once()
    # ... and the whole burst was drained
    assert await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"]) == []


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_drain_coalesces_mixed_changed_columns_of_the_same_aggregate(
    sqlalchemy_async_engine: AsyncEngine,
    mock_project_subsystem: dict[str, mock.Mock],
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    """Coalescing must preserve *all* projection branches: an outputs event and a
    state event for the same aggregate become one projection that refreshes both."""
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=faker.uuid4(),
        outputs={},
        node_class=NodeClass.COMPUTATIONAL,
    )
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
        )
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(state=StateType.ABORTED).where(comp_tasks.c.task_id == task["task_id"])
        )

    rows_before = await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"])
    assert len(rows_before) == 2

    await claim_and_process_outbox_events(client.app, sqlalchemy_async_engine)

    # both branches ran exactly once for the coalesced pair
    mock_project_subsystem["update_node_outputs"].assert_called_once()
    assert mock_project_subsystem["update_node_outputs"].await_args.kwargs["strict_notification"]
    mock_project_subsystem["_update_project_state.update_project_node_state"].assert_called_once()
    mock_project_subsystem["_update_project_state.notify_project_node_update"].assert_called_once()
    mock_project_subsystem["_update_project_state.notify_project_state_update"].assert_called_once()
    assert mock_project_subsystem["_update_project_state.notify_project_node_update"].await_args.kwargs["strict"]
    assert mock_project_subsystem["_update_project_state.notify_project_state_update"].await_args.kwargs["strict"]
    assert await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"]) == []
