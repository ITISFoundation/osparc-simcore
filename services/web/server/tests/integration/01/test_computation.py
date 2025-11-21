# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments


import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from copy import deepcopy
from pathlib import Path
from typing import Any, NamedTuple

import pytest
import socketio
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from common_library.json_serialization import json_dumps
from faker import Faker
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.rpc.webserver import DEFAULT_WEBSERVER_RPC_NAMESPACE
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from servicelib.aiohttp import status
from servicelib.aiohttp.application import create_safe_application
from servicelib.status_codes_utils import get_code_display_name
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_postgres_database.models.comp_runs_collections import comp_runs_collections
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_metadata import projects_metadata
from simcore_postgres_database.models.users import UserRole
from simcore_postgres_database.webserver_models import (
    NodeClass,
    StateType,
    comp_pipeline,
    comp_tasks,
)
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.db.plugin import setup_db
from simcore_service_webserver.db_listener._utils import DB_TO_RUNNING_STATE
from simcore_service_webserver.db_listener.plugin import setup_db_listener
from simcore_service_webserver.diagnostics.plugin import setup_diagnostics
from simcore_service_webserver.director_v2.plugin import setup_director_v2
from simcore_service_webserver.login.plugin import setup_login
from simcore_service_webserver.notifications.plugin import setup_notifications
from simcore_service_webserver.products.plugin import setup_products
from simcore_service_webserver.projects.plugin import setup_projects
from simcore_service_webserver.resource_manager.plugin import setup_resource_manager
from simcore_service_webserver.rest.plugin import setup_rest
from simcore_service_webserver.security.plugin import setup_security
from simcore_service_webserver.session.plugin import setup_session
from simcore_service_webserver.socketio.messages import SOCKET_IO_NODE_UPDATED_EVENT
from simcore_service_webserver.socketio.plugin import setup_socketio
from simcore_service_webserver.users.plugin import setup_users
from sqlalchemy.ext.asyncio import AsyncEngine
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL

# Selection of core and tool services started in this swarm fixture (integration)
pytest_simcore_core_services_selection = [
    "catalog",
    "dask-scheduler",
    "dask-sidecar",
    "docker-api-proxy",
    "dynamic-schdlr",
    "director-v2",
    "director",
    "migration",
    "postgres",
    "rabbit",
    "redis",
    "storage",
]

pytest_simcore_ops_services_selection = [
    "minio",
    "adminer",
]


class _ExpectedResponseTuple(NamedTuple):
    """
    Stores respons status to an API request in function of the user

    e.g. for a request that normally returns OK, a non-authorized user
    will have no access, therefore ExpectedResponse.ok = HTTPUnauthorized
    """

    ok: int
    created: int
    no_content: int
    confict: int

    # pylint: disable=no-member
    def __str__(self) -> str:
        items = ", ".join(
            f"{k}={get_code_display_name(c)}" for k, c in self._asdict().items()
        )
        return f"{self.__class__.__name__}({items})"


def user_role_response():
    return (
        "user_role,expected",
        [
            pytest.param(
                UserRole.USER,
                _ExpectedResponseTuple(
                    ok=status.HTTP_200_OK,
                    created=status.HTTP_201_CREATED,
                    no_content=status.HTTP_204_NO_CONTENT,
                    confict=status.HTTP_409_CONFLICT,
                ),
            ),
        ],
    )


@pytest.fixture
async def client(
    sqlalchemy_async_engine: AsyncEngine,
    rabbit_service: RabbitSettings,
    redis_settings: RedisSettings,
    aiohttp_client: Callable,
    app_config: dict[str, Any],  # waits until swarm with *_services are up
    monkeypatch_setenv_from_app_config: Callable,
    simcore_services_ready: None,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    cfg = deepcopy(app_config)

    assert cfg["rest"]["version"] == API_VTAG

    cfg["storage"]["enabled"] = False
    cfg["main"]["testing"] = True

    # fake config
    monkeypatch_setenv_from_app_config(cfg)
    setenvs_from_dict(
        monkeypatch,
        envs={
            "WEBSERVER_RPC_NAMESPACE": DEFAULT_WEBSERVER_RPC_NAMESPACE,
        },
    )

    app = create_safe_application(app_config)

    assert setup_settings(app)
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_diagnostics(app)
    setup_login(app)
    setup_users(app)
    setup_socketio(app)
    setup_projects(app)
    setup_notifications(app)
    setup_director_v2(app)
    setup_resource_manager(app)
    setup_products(app)
    setup_db_listener(app)
    # no garbage collector

    return await aiohttp_client(
        app,
        server_kwargs={
            "port": app_config["main"]["port"],
            "host": app_config["main"]["host"],
        },
    )


@pytest.fixture(scope="session")
def fake_workbench_adjacency_list(tests_data_dir: Path) -> dict[str, Any]:
    file_path = tests_data_dir / "workbench_sleeper_dag_adjacency_list.json"
    with file_path.open() as fp:
        return json.load(fp)


async def _assert_db_contents(
    project_id: str,
    sqlalchemy_async_engine: AsyncEngine,
    fake_workbench_payload: dict[str, Any],
    fake_workbench_adjacency_list: dict[str, Any],
    check_outputs: bool,
) -> None:
    async with sqlalchemy_async_engine.connect() as conn:
        pipeline_db = (
            await conn.execute(
                sa.select(comp_pipeline).where(comp_pipeline.c.project_id == project_id)
            )
        ).one()

        assert pipeline_db.project_id == project_id
        assert pipeline_db.dag_adjacency_list == fake_workbench_adjacency_list

        # check db comp_tasks
        tasks_db = (
            await conn.execute(
                sa.select(comp_tasks).where(comp_tasks.c.project_id == project_id)
            )
        ).all()
        assert tasks_db

        mock_pipeline = fake_workbench_payload
        assert len(tasks_db) == len(mock_pipeline)

        for task_db in tasks_db:
            assert task_db.project_id == project_id
            assert task_db.node_id in mock_pipeline

            assert task_db.inputs == mock_pipeline[task_db.node_id].get("inputs")

            if check_outputs:
                assert task_db.outputs == mock_pipeline[task_db.node_id].get("outputs")

            assert task_db.image["name"] == mock_pipeline[task_db.node_id]["key"]
            assert task_db.image["tag"] == mock_pipeline[task_db.node_id]["version"]


NodeIdStr = str


async def _get_computational_tasks_from_db(
    project_id: str,
    sqlalchemy_async_engine: AsyncEngine,
) -> dict[NodeIdStr, Any]:
    # this check is only there to check the comp_pipeline is there
    async with sqlalchemy_async_engine.connect() as conn:
        assert (
            await conn.execute(
                sa.select(comp_pipeline).where(comp_pipeline.c.project_id == project_id)
            )
        ).one(), f"missing pipeline in the database under comp_pipeline {project_id}"

        # get the computational tasks
        tasks_db = (
            await conn.execute(
                sa.select(comp_tasks).where(
                    (comp_tasks.c.project_id == project_id)
                    & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
                )
            )
        ).all()

    print(f"--> tasks from DB: {tasks_db=}")
    return {t.node_id: t for t in tasks_db}


async def _get_project_workbench_from_db(
    project_id: str,
    sqlalchemy_async_engine: AsyncEngine,
) -> dict[str, Any]:
    # this check is only there to check the comp_pipeline is there
    print(f"--> looking for project {project_id=} in projects table...")
    async with sqlalchemy_async_engine.connect() as conn:
        project_in_db = (
            await conn.execute(sa.select(projects).where(projects.c.uuid == project_id))
        ).one()

    print(
        f"<-- found following workbench: {json_dumps(project_in_db.workbench, indent=2)}"
    )
    return project_in_db.workbench


async def _assert_and_wait_for_pipeline_state(
    client: TestClient,
    project_id: str,
    expected_state: RunningState,
    expected_api_response: _ExpectedResponseTuple,
) -> None:
    assert client.app
    url_project_state = client.app.router["get_project_state"].url_for(
        project_id=project_id
    )
    assert url_project_state == URL(f"/{API_VTAG}/projects/{project_id}/state")
    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_delay(120),
        wait=wait_fixed(5),
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            print(
                f"--> waiting for pipeline to complete with {expected_state=} attempt {attempt.retry_state.attempt_number}..."
            )
            resp = await client.get(f"{url_project_state}")
            data, error = await assert_status(resp, expected_api_response.ok)
            assert "state" in data
            assert "value" in data["state"]
            received_study_state = RunningState(data["state"]["value"])
            print(f"<-- received pipeline state: {received_study_state=}")
            assert received_study_state == expected_state
            print(
                f"--> pipeline completed with state {received_study_state=}! "
                f"That's great: {json_dumps(attempt.retry_state.retry_object.statistics)}",
            )


async def _assert_and_wait_for_comp_task_states_to_be_transmitted_in_projects(
    project_id: str,
    sqlalchemy_async_engine: AsyncEngine,
) -> None:
    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_delay(120),
        wait=wait_fixed(5),
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            print(
                f"--> waiting for pipeline results to move to projects table, attempt {attempt.retry_state.attempt_number}..."
            )
            comp_tasks_in_db: dict[NodeIdStr, Any] = (
                await _get_computational_tasks_from_db(
                    project_id, sqlalchemy_async_engine
                )
            )
            workbench_in_db: dict[NodeIdStr, Any] = (
                await _get_project_workbench_from_db(
                    project_id, sqlalchemy_async_engine
                )
            )
            for node_id, node_values in comp_tasks_in_db.items():
                assert (
                    node_id in workbench_in_db
                ), f"node {node_id=} is missing from workbench {json_dumps(workbench_in_db, indent=2)}"

                node_in_project_table = workbench_in_db[node_id]

                # if this one is in, the other should also be but let's check it carefully
                assert node_values.run_hash
                assert "runHash" in node_in_project_table
                assert node_values.run_hash == node_in_project_table["runHash"]

                assert node_values.state
                assert "state" in node_in_project_table
                assert "currentStatus" in node_in_project_table["state"]
                # NOTE: beware that the comp_tasks has StateType and Workbench has RunningState (sic)
                assert (
                    DB_TO_RUNNING_STATE[node_values.state].value
                    == node_in_project_table["state"]["currentStatus"]
                )
            print(
                "--> tasks were properly transferred! "
                f"That's great: {json_dumps(attempt.retry_state.retry_object.statistics)}",
            )


@pytest.mark.parametrize(*user_role_response(), ids=str)
async def test_start_stop_computation(
    client: TestClient,
    sleeper_service: dict[str, str],
    sqlalchemy_async_engine: AsyncEngine,
    logged_user: dict[str, Any],
    user_project: dict[str, Any],
    fake_workbench_adjacency_list: dict[str, Any],
    user_role: UserRole,
    expected: _ExpectedResponseTuple,
):
    assert client.app
    project_id = user_project["uuid"]
    fake_workbench_payload = user_project["workbench"]

    url_start = client.app.router["start_computation"].url_for(project_id=project_id)
    assert url_start == URL(f"/{API_VTAG}/computations/{project_id}:start")

    # POST /v0/computations/{project_id}:start
    resp = await client.post(f"{url_start}")
    data, error = await assert_status(resp, expected.created)

    if not error:
        # starting again should be disallowed, since it's already running
        resp = await client.post(f"{url_start}")
        assert resp.status == expected.confict

        assert "pipeline_id" in data
        assert data["pipeline_id"] == project_id

        await _assert_db_contents(
            project_id,
            sqlalchemy_async_engine,
            fake_workbench_payload,
            fake_workbench_adjacency_list,
            check_outputs=False,
        )
        # wait for the computation to complete successfully
        await _assert_and_wait_for_pipeline_state(
            client, project_id, RunningState.SUCCESS, expected
        )
        # we need to wait until the webserver has updated the projects DB before starting another round
        await _assert_and_wait_for_comp_task_states_to_be_transmitted_in_projects(
            project_id, sqlalchemy_async_engine
        )
        # restart the computation, this should produce a 422 since the computation was complete
        resp = await client.post(f"{url_start}")
        assert resp.status == status.HTTP_422_UNPROCESSABLE_ENTITY
        # force restart the computation
        resp = await client.post(f"{url_start}", json={"force_restart": True})
        data, error = await assert_status(resp, expected.created)
        assert not error

    # give it time to run a bit ... before cancelling the run
    await asyncio.sleep(5)

    # now stop the pipeline
    # POST /v0/computations/{project_id}:stop
    url_stop = client.app.router["stop_computation"].url_for(project_id=project_id)
    assert url_stop == URL(f"/{API_VTAG}/computations/{project_id}:stop")
    resp = await client.post(f"{url_stop}")
    data, error = await assert_status(resp, expected.no_content)
    if not error:
        # now wait for it to stop
        await _assert_and_wait_for_pipeline_state(
            client, project_id, RunningState.ABORTED, expected
        )
        # we need to wait until the webserver has updated the projects DB
        await _assert_and_wait_for_comp_task_states_to_be_transmitted_in_projects(
            project_id, sqlalchemy_async_engine
        )


@pytest.mark.parametrize(*user_role_response(), ids=str)
async def test_run_pipeline_and_check_state(
    client: TestClient,
    sleeper_service: dict[str, str],
    sqlalchemy_async_engine: AsyncEngine,
    # logged_user: dict[str, Any],
    user_project: dict[str, Any],
    fake_workbench_adjacency_list: dict[str, Any],
    # user_role: UserRole,
    expected: _ExpectedResponseTuple,
):
    assert client.app
    project_id = user_project["uuid"]
    fake_workbench_payload = user_project["workbench"]

    url_start = client.app.router["start_computation"].url_for(project_id=project_id)
    assert url_start == URL(f"/{API_VTAG}/computations/{project_id}:start")

    # POST /v0/computations/{project_id}:start
    resp = await client.post(f"{url_start}")
    data, error = await assert_status(resp, expected.created)

    if error:
        return

    assert "pipeline_id" in data
    assert data["pipeline_id"] == project_id

    await _assert_db_contents(
        project_id,
        sqlalchemy_async_engine,
        fake_workbench_payload,
        fake_workbench_adjacency_list,
        check_outputs=False,
    )

    url_project_state = client.app.router["get_project_state"].url_for(
        project_id=project_id
    )
    assert url_project_state == URL(f"/{API_VTAG}/projects/{project_id}/state")

    running_state_order_lookup = {
        RunningState.UNKNOWN: 0,
        RunningState.NOT_STARTED: 1,
        RunningState.PUBLISHED: 2,
        RunningState.WAITING_FOR_CLUSTER: 2,
        RunningState.PENDING: 3,
        RunningState.WAITING_FOR_RESOURCES: 3,
        RunningState.STARTED: 4,
        RunningState.SUCCESS: 5,
        RunningState.FAILED: 5,
        RunningState.ABORTED: 5,
    }

    members = [k in running_state_order_lookup for k in RunningState.__members__]
    assert all(
        members
    ), "there are missing members in the order lookup, please complete!"

    pipeline_state = RunningState.UNKNOWN

    start = time.monotonic()
    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_delay(120),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(ValueError),
    ):
        with attempt:
            print(
                f"--> waiting for pipeline to complete attempt {attempt.retry_state.attempt_number}..."
            )
            resp = await client.get(f"{url_project_state}")
            data, error = await assert_status(resp, expected.ok)
            assert "state" in data
            assert "value" in data["state"]
            received_study_state = RunningState(data["state"]["value"])
            print(f"--> project computation state {received_study_state=}")
            assert (
                running_state_order_lookup[received_study_state]
                >= running_state_order_lookup[pipeline_state]
            ), (
                f"the received state {received_study_state} shall be greater "
                f"or equal to the previous state {pipeline_state}"
            )
            assert received_study_state not in [
                RunningState.ABORTED,
                RunningState.FAILED,
            ], "the pipeline did not end up successfully"
            pipeline_state = received_study_state
            if received_study_state != RunningState.SUCCESS:
                raise ValueError
            print(
                f"--> pipeline completed with state {received_study_state=}! That's great: {json_dumps(attempt.retry_state.retry_object.statistics)}",
            )
    assert pipeline_state == RunningState.SUCCESS
    comp_tasks_in_db: dict[NodeIdStr, Any] = await _get_computational_tasks_from_db(
        project_id, sqlalchemy_async_engine
    )
    is_success = [t.state == StateType.SUCCESS for t in comp_tasks_in_db.values()]
    assert all(is_success), (
        "the individual computational services are not finished! "
        f"Expected to be completed, got {comp_tasks_in_db=}"
    )
    # we need to wait until the webserver has updated the projects DB
    await _assert_and_wait_for_comp_task_states_to_be_transmitted_in_projects(
        project_id, sqlalchemy_async_engine
    )

    print(f"<-- pipeline completed successfully in {time.monotonic() - start} seconds")


@pytest.fixture
async def populated_project_metadata(
    client: TestClient,
    logged_user: dict[str, Any],
    user_project: dict[str, Any],
    faker: Faker,
    sqlalchemy_async_engine: AsyncEngine,
):
    assert client.app
    project_uuid = user_project["uuid"]
    async with sqlalchemy_async_engine.begin() as con:
        await con.execute(
            projects_metadata.insert().values(
                project_uuid=project_uuid,
                custom={
                    "job_name": "My Job Name",
                    "group_id": faker.uuid4(),
                    "group_name": "My Group Name",
                },
            )
        )
        yield
    async with sqlalchemy_async_engine.begin() as con:
        await con.execute(projects_metadata.delete())
        await con.execute(comp_runs_collections.delete())  # cleanup


@pytest.mark.parametrize(*user_role_response(), ids=str)
async def test_start_multiple_computation_with_the_same_collection_run_id(
    client: TestClient,
    sleeper_service: dict[str, str],
    sqlalchemy_async_engine: AsyncEngine,
    populated_project_metadata: None,
    logged_user: dict[str, Any],
    user_project: dict[str, Any],
    fake_workbench_adjacency_list: dict[str, Any],
    user_role: UserRole,
    expected: _ExpectedResponseTuple,
):
    assert client.app
    project_id = user_project["uuid"]

    url_start = client.app.router["start_computation"].url_for(project_id=project_id)
    assert url_start == URL(f"/{API_VTAG}/computations/{project_id}:start")

    # POST /v0/computations/{project_id}:start
    resp = await client.post(f"{url_start}")
    await assert_status(resp, expected.created)

    resp = await client.post(f"{url_start}")
    # starting again should be disallowed, since it's already running
    assert resp.status == expected.confict

    # NOTE: This tests that there is only one entry in comp_runs_collections table created
    # as the project metadata has the same group_id


@pytest.mark.parametrize(*user_role_response(), ids=str)
async def test_running_computation_sends_progress_updates_via_socketio(
    client: TestClient,
    sleeper_service: dict[str, str],
    sqlalchemy_async_engine: AsyncEngine,
    logged_user: dict[str, Any],
    user_project: dict[str, Any],
    fake_workbench_adjacency_list: dict[str, Any],
    expected: _ExpectedResponseTuple,
    create_socketio_connection: Callable[
        [str | None, TestClient | None], Awaitable[tuple[socketio.AsyncClient, str]]
    ],
    mocker: MockerFixture,
):
    assert client.app
    socket_io_conn, client_id = await create_socketio_connection(None, client)
    mock_node_updated_handler = mocker.MagicMock()
    socket_io_conn.on(SOCKET_IO_NODE_UPDATED_EVENT, handler=mock_node_updated_handler)

    project_id = user_project["uuid"]

    # NOTE: we need to open the project so that the computation pipeline messages are transmitted and we get all the node updates
    url_open = client.app.router["open_project"].url_for(project_id=project_id)
    assert url_open == URL(f"/{API_VTAG}/projects/{project_id}:open")
    resp = await client.post(f"{url_open}", json=client_id)
    data, error = await assert_status(resp, expected.ok)

    # start the computation
    url_start = client.app.router["start_computation"].url_for(project_id=project_id)
    assert url_start == URL(f"/{API_VTAG}/computations/{project_id}:start")

    # POST /v0/computations/{project_id}:start
    resp = await client.post(f"{url_start}")
    data, error = await assert_status(resp, status.HTTP_201_CREATED)
    assert not error

    assert "pipeline_id" in data
    assert data["pipeline_id"] == project_id

    await _assert_db_contents(
        project_id,
        sqlalchemy_async_engine,
        user_project["workbench"],
        fake_workbench_adjacency_list,
        check_outputs=False,
    )

    # wait for the computation to complete successfully
    await _assert_and_wait_for_pipeline_state(
        client,
        project_id,
        RunningState.SUCCESS,
        expected,
    )

    # check that the progress updates were sent
    assert mock_node_updated_handler.call_count > 0, (
        "expected progress updates to be sent via socketio, "
        f"but got {mock_node_updated_handler.call_count} calls"
    )

    # Get all computational nodes from the workbench (exclude file-picker nodes)
    computational_node_ids = {
        node_id
        for node_id, node_data in user_project["workbench"].items()
        if node_data.get("key", "").startswith("simcore/services/comp/")
    }

    # Collect all node IDs that received progress updates
    received_progress_node_ids = set()
    for call_args in mock_node_updated_handler.call_args_list:
        assert len(call_args[0]) == 1, (
            "expected the progress handler to be called with a single argument, "
            f"but got {len(call_args[0])} arguments"
        )
        message = call_args[0][0]
        assert "node_id" in message
        assert "project_id" in message
        assert "data" in message
        assert "errors" in message
        node_data = TypeAdapter(Node).validate_python(message["data"])
        assert node_data

        received_progress_node_ids.add(message["node_id"])

    # Verify that progress updates were sent for ALL computational nodes
    missing_nodes = computational_node_ids - received_progress_node_ids
    assert not missing_nodes, (
        f"expected progress updates for all computational nodes {computational_node_ids}, "
        f"but missing updates for {missing_nodes}. "
        f"Received updates for: {received_progress_node_ids}"
    )

    # check that a node update was sent for each computational node at the end that unlocks the node
    node_id_data_map: dict[NodeID, list[Node]] = {}
    for mock_call in mock_node_updated_handler.call_args_list:
        node_id = NodeID(mock_call[0][0]["node_id"])
        node_data = TypeAdapter(Node).validate_python(mock_call[0][0]["data"])
        node_id_data_map.setdefault(node_id, []).append(node_data)

    for node_id, node_data_list in node_id_data_map.items():
        # find the last update for this node
        last_node_data = node_data_list[-1]
        assert last_node_data.state
        assert last_node_data.state.current_status == RunningState.SUCCESS
        assert last_node_data.state.lock_state
        assert last_node_data.state.lock_state.locked is False, (
            f"expected node {node_id} to be unlocked at the end of the pipeline, "
            "but it is still locked."
        )
