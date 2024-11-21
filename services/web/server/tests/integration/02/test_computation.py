# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments


import asyncio
import json
import time
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any, NamedTuple

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from common_library.json_serialization import json_dumps
from models_library.projects_state import RunningState
from pytest_simcore.helpers.assert_checks import assert_status
from servicelib.aiohttp import status
from servicelib.aiohttp.application import create_safe_application
from servicelib.status_codes_utils import get_code_display_name
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_postgres_database.models.projects import projects
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
from simcore_service_webserver.socketio.plugin import setup_socketio
from simcore_service_webserver.users.plugin import setup_users
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
def client(
    event_loop: asyncio.AbstractEventLoop,
    postgres_db: sa.engine.Engine,
    rabbit_service: RabbitSettings,
    redis_settings: RedisSettings,
    aiohttp_client: Callable,
    app_config: dict[str, Any],  # waits until swarm with *_services are up
    monkeypatch_setenv_from_app_config: Callable,
    simcore_services_ready: None,
) -> TestClient:
    cfg = deepcopy(app_config)

    assert cfg["rest"]["version"] == API_VTAG

    cfg["storage"]["enabled"] = False
    cfg["main"]["testing"] = True

    # fake config
    monkeypatch_setenv_from_app_config(cfg)
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

    return event_loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={
                "port": app_config["main"]["port"],
                "host": app_config["main"]["host"],
            },
        )
    )


@pytest.fixture(scope="session")
def fake_workbench_adjacency_list(tests_data_dir: Path) -> dict[str, Any]:
    file_path = tests_data_dir / "workbench_sleeper_dag_adjacency_list.json"
    with file_path.open() as fp:
        return json.load(fp)


def _assert_db_contents(
    project_id: str,
    postgres_db: sa.engine.Engine,
    fake_workbench_payload: dict[str, Any],
    fake_workbench_adjacency_list: dict[str, Any],
    check_outputs: bool,
) -> None:
    with postgres_db.connect() as conn:
        pipeline_db = conn.execute(
            sa.select(comp_pipeline).where(comp_pipeline.c.project_id == project_id)
        ).fetchone()
        assert pipeline_db

        assert pipeline_db[comp_pipeline.c.project_id] == project_id
        assert (
            pipeline_db[comp_pipeline.c.dag_adjacency_list]
            == fake_workbench_adjacency_list
        )

        # check db comp_tasks
        tasks_db = conn.execute(
            sa.select(comp_tasks).where(comp_tasks.c.project_id == project_id)
        ).fetchall()
        assert tasks_db

        mock_pipeline = fake_workbench_payload
        assert len(tasks_db) == len(mock_pipeline)

        for task_db in tasks_db:
            assert task_db.project_id == project_id
            assert task_db.node_id in mock_pipeline.keys()

            assert task_db.inputs == mock_pipeline[task_db.node_id].get("inputs")

            if check_outputs:
                assert task_db.outputs == mock_pipeline[task_db.node_id].get("outputs")

            assert task_db.image["name"] == mock_pipeline[task_db.node_id]["key"]
            assert task_db.image["tag"] == mock_pipeline[task_db.node_id]["version"]


NodeIdStr = str


def _get_computational_tasks_from_db(
    project_id: str,
    postgres_db: sa.engine.Engine,
) -> dict[NodeIdStr, Any]:
    # this check is only there to check the comp_pipeline is there
    with postgres_db.connect() as conn:
        assert (
            conn.execute(
                sa.select(comp_pipeline).where(comp_pipeline.c.project_id == project_id)
            ).fetchone()
            is not None
        ), f"missing pipeline in the database under comp_pipeline {project_id}"

        # get the computational tasks
        tasks_db = conn.execute(
            sa.select(comp_tasks).where(
                (comp_tasks.c.project_id == project_id)
                & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
            )
        ).fetchall()

    print(f"--> tasks from DB: {tasks_db=}")
    return {t.node_id: t for t in tasks_db}


def _get_project_workbench_from_db(
    project_id: str,
    postgres_db: sa.engine.Engine,
) -> dict[str, Any]:
    # this check is only there to check the comp_pipeline is there
    print(f"--> looking for project {project_id=} in projects table...")
    with postgres_db.connect() as conn:
        project_in_db = conn.execute(
            sa.select(projects).where(projects.c.uuid == project_id)
        ).fetchone()

    assert (
        project_in_db
    ), f"missing pipeline in the database under comp_pipeline {project_id}"
    print(
        f"<-- found following workbench: {json_dumps( project_in_db.workbench, indent=2)}"
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
    postgres_db: sa.engine.Engine,
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
            comp_tasks_in_db: dict[NodeIdStr, Any] = _get_computational_tasks_from_db(
                project_id, postgres_db
            )
            workbench_in_db: dict[NodeIdStr, Any] = _get_project_workbench_from_db(
                project_id, postgres_db
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
    postgres_db: sa.engine.Engine,
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

        _assert_db_contents(
            project_id,
            postgres_db,
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
            project_id, postgres_db
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
            project_id, postgres_db
        )


@pytest.mark.parametrize(*user_role_response(), ids=str)
async def test_run_pipeline_and_check_state(
    client: TestClient,
    sleeper_service: dict[str, str],
    postgres_db: sa.engine.Engine,
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

    _assert_db_contents(
        project_id,
        postgres_db,
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
    comp_tasks_in_db: dict[NodeIdStr, Any] = _get_computational_tasks_from_db(
        project_id, postgres_db
    )
    is_success = [t.state == StateType.SUCCESS for t in comp_tasks_in_db.values()]
    assert all(is_success), (
        "the individual computational services are not finished! "
        f"Expected to be completed, got {comp_tasks_in_db=}"
    )
    # we need to wait until the webserver has updated the projects DB
    await _assert_and_wait_for_comp_task_states_to_be_transmitted_in_projects(
        project_id, postgres_db
    )

    print(f"<-- pipeline completed successfully in {time.monotonic() - start} seconds")
