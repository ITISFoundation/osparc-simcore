# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import asyncio
import json
import sys
from collections import namedtuple
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import pytest
import socketio
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.settings.rabbit import RabbitConfig
from models_library.settings.redis import RedisConfig
from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.aiohttp.application import create_safe_application
from simcore_postgres_database.webserver_models import (
    NodeClass,
    StateType,
    comp_pipeline,
    comp_tasks,
)
from simcore_service_webserver.computation import setup_computation
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.director_v2 import setup_director_v2
from simcore_service_webserver.login.module_setup import setup_login
from simcore_service_webserver.projects.module_setup import setup_projects
from simcore_service_webserver.projects.projects_handlers import HTTPLocked
from simcore_service_webserver.resource_manager.module_setup import (
    setup_resource_manager,
)
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio.module_setup import setup_socketio
from simcore_service_webserver.users import setup_users
from socketio.exceptions import ConnectionError as SocketConnectionError
from tenacity import retry
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL

API_VERSION = "v0"
API_PREFIX = "/" + API_VERSION


# Selection of core and tool services started in this swarm fixture (integration)
pytest_simcore_core_services_selection = [
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

pytest_simcore_ops_services_selection = ["minio", "adminer"]


# HELPERS ----------------------------------------------------------------------------

ExpectedResponse = namedtuple(
    "ExpectedResponse",
    ["ok", "created", "no_content", "not_found", "forbidden", "locked", "accepted"],
)


def standard_role_response() -> Tuple[str, List[Tuple[UserRole, ExpectedResponse]]]:
    return (
        "user_role,expected",
        [
            (
                UserRole.ANONYMOUS,
                ExpectedResponse(
                    web.HTTPUnauthorized,
                    web.HTTPUnauthorized,
                    web.HTTPUnauthorized,
                    web.HTTPUnauthorized,
                    web.HTTPUnauthorized,
                    web.HTTPUnauthorized,
                    web.HTTPUnauthorized,
                ),
            ),
            (
                UserRole.GUEST,
                ExpectedResponse(
                    web.HTTPForbidden,
                    web.HTTPForbidden,
                    web.HTTPForbidden,
                    web.HTTPForbidden,
                    web.HTTPForbidden,
                    web.HTTPForbidden,
                    web.HTTPForbidden,
                ),
            ),
            (
                UserRole.USER,
                ExpectedResponse(
                    web.HTTPOk,
                    web.HTTPCreated,
                    web.HTTPNoContent,
                    web.HTTPNotFound,
                    web.HTTPForbidden,
                    HTTPLocked,
                    web.HTTPAccepted,
                ),
            ),
            (
                UserRole.TESTER,
                ExpectedResponse(
                    web.HTTPOk,
                    web.HTTPCreated,
                    web.HTTPNoContent,
                    web.HTTPNotFound,
                    web.HTTPForbidden,
                    HTTPLocked,
                    web.HTTPAccepted,
                ),
            ),
        ],
    )


# FIXTURES ----------------------------------------------------------------------------


@pytest.fixture
def client(
    loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    app_config: Dict[str, Any],  ## waits until swarm with *_services are up
) -> TestClient:
    assert app_config["rest"]["version"] == API_VERSION

    app_config["storage"]["enabled"] = False
    app_config["main"]["testing"] = True

    # fake config
    app = create_safe_application(app_config)

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_users(app)
    setup_socketio(app)
    setup_projects(app)
    setup_computation(app)
    setup_director_v2(app)
    setup_resource_manager(app)

    return loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={
                "port": app_config["main"]["port"],
                "host": app_config["main"]["host"],
            },
        )
    )


@pytest.fixture(scope="session")
def mock_workbench_adjacency_list(tests_data_dir: Path) -> Dict[str, Any]:
    file_path = tests_data_dir / "workbench_sleeper_dag_adjacency_list.json"
    with file_path.open() as fp:
        return json.load(fp)


# HELPERS ----------------------------------
def _assert_db_contents(
    project_id: str,
    postgres_session: sa.orm.session.Session,
    mock_workbench_payload: Dict[str, Any],
    mock_workbench_adjacency_list: Dict[str, Any],
    check_outputs: bool,
):
    # pylint: disable=no-member
    pipeline_db = (
        postgres_session.query(comp_pipeline)
        .filter(comp_pipeline.c.project_id == project_id)
        .one()
    )
    assert pipeline_db.project_id == project_id
    assert pipeline_db.dag_adjacency_list == mock_workbench_adjacency_list

    # check db comp_tasks
    tasks_db = (
        postgres_session.query(comp_tasks)
        .filter(comp_tasks.c.project_id == project_id)
        .all()
    )
    mock_pipeline = mock_workbench_payload
    assert len(tasks_db) == len(mock_pipeline)

    for task_db in tasks_db:
        # assert task_db.task_id == (i+1)
        assert task_db.project_id == project_id
        assert task_db.node_id in mock_pipeline.keys()

        assert task_db.inputs == mock_pipeline[task_db.node_id].get("inputs")

        if check_outputs:
            assert task_db.outputs == mock_pipeline[task_db.node_id].get("outputs")

        assert task_db.image["name"] == mock_pipeline[task_db.node_id]["key"]
        assert task_db.image["tag"] == mock_pipeline[task_db.node_id]["version"]


def _assert_sleeper_services_completed(
    project_id: str,
    postgres_session: sa.orm.session.Session,
    expected_state: StateType,
    mock_workbench_payload: Dict[str, Any],
):
    # pylint: disable=no-member
    TIMEOUT_SECONDS = 60
    WAIT_TIME = 1
    NUM_COMP_TASKS_TO_WAIT_FOR = len(
        [x for x in mock_workbench_payload.values() if "/comp/" in x["key"]]
    )

    @retry(
        reraise=True,
        stop=stop_after_delay(TIMEOUT_SECONDS),
        wait=wait_fixed(WAIT_TIME),
        retry=retry_if_exception_type(AssertionError),
    )
    def check_pipeline_results():
        # this check is only there to check the comp_pipeline is there
        assert (
            postgres_session.query(comp_pipeline)
            .filter(comp_pipeline.c.project_id == project_id)
            .one()
        ), f"missing pipeline in the database under comp_pipeline {project_id}"

        # get the tasks that should be completed either by being aborted, successfuly completed or failed
        tasks_db = (
            postgres_session.query(comp_tasks)
            .filter(
                (comp_tasks.c.project_id == project_id)
                & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
                & (
                    # these are the options of a completed pipeline
                    (comp_tasks.c.state == StateType.ABORTED)
                    | (comp_tasks.c.state == StateType.SUCCESS)
                    | (comp_tasks.c.state == StateType.FAILED)
                )
            )
            .all()
        )
        # check that all computational tasks are completed
        assert (
            len(tasks_db) == NUM_COMP_TASKS_TO_WAIT_FOR
        ), f"all tasks have not finished, expected {NUM_COMP_TASKS_TO_WAIT_FOR}, got {len(tasks_db)}"
        # get the different states in a set of states
        set_of_states = {task_db.state for task_db in tasks_db}
        if expected_state in [StateType.ABORTED, StateType.FAILED]:
            # only one is necessary
            assert (
                expected_state in set_of_states
            ), f"{expected_state} not found in {set_of_states}"
        else:
            assert not any(
                x in set_of_states
                for x in [
                    StateType.PUBLISHED,
                    StateType.PENDING,
                    StateType.NOT_STARTED,
                ]
            ), f"pipeline did not start yet... {set_of_states}"

            assert (
                len(set_of_states) == 1
            ), f"there are more than one state in {set_of_states}"

            assert (
                expected_state in set_of_states
            ), f"{expected_state} not found in {set_of_states}"

    check_pipeline_results()


# TESTS ------------------------------------------
@pytest.mark.parametrize(
    *standard_role_response(),
)
async def test_start_pipeline(
    sleeper_service: Dict[str, str],
    postgres_session: sa.orm.session.Session,
    rabbit_service: RabbitConfig,
    redis_service: RedisConfig,
    simcore_services_ready: None,
    client: TestClient,
    socketio_client_factory: Callable[
        [Optional[str], Optional[TestClient]], Awaitable[socketio.AsyncClient]
    ],
    logged_user: Dict[str, Any],
    user_project: Dict[str, Any],
    mock_workbench_adjacency_list: Dict[str, Any],
    user_role: UserRole,
    expected: ExpectedResponse,
):
    project_id = user_project["uuid"]
    mock_workbench_payload = user_project["workbench"]
    # connect websocket (to prevent the GC to remove the project)
    try:
        sio = await socketio_client_factory(None, None)
        assert sio.sid
    except SocketConnectionError:
        if expected.created == web.HTTPCreated:
            pytest.fail("socket io connection should not fail")

    url_start = client.app.router["start_pipeline"].url_for(project_id=project_id)
    assert url_start == URL(
        API_PREFIX + "/computation/pipeline/{}:start".format(project_id)
    )

    # POST /v0/computation/pipeline/{project_id}:start
    resp = await client.post(f"{url_start}")
    data, error = await assert_status(
        resp, web.HTTPCreated if user_role == UserRole.GUEST else expected.created
    )

    if not error:
        # starting again should be disallowed, since it's already running
        resp = await client.post(f"{url_start}")
        assert (
            resp.status == web.HTTPForbidden.status_code
            if user_role == UserRole.GUEST
            else expected.forbidden.status_code
        )

        assert "pipeline_id" in data
        assert data["pipeline_id"] == project_id

        _assert_db_contents(
            project_id,
            postgres_session,
            mock_workbench_payload,
            mock_workbench_adjacency_list,
            check_outputs=False,
        )
        # wait for the computation to stop
        _assert_sleeper_services_completed(
            project_id, postgres_session, StateType.SUCCESS, mock_workbench_payload
        )
        # restart the computation
        resp = await client.post(f"{url_start}")
        data, error = await assert_status(
            resp, web.HTTPCreated if user_role == UserRole.GUEST else expected.created
        )
        assert not error
    # now stop the pipeline
    # POST /v0/computation/pipeline/{project_id}:stop
    url_stop = client.app.router["stop_pipeline"].url_for(project_id=project_id)
    assert url_stop == URL(
        API_PREFIX + "/computation/pipeline/{}:stop".format(project_id)
    )
    await asyncio.sleep(2)
    resp = await client.post(f"{url_stop}")
    data, error = await assert_status(
        resp, web.HTTPNoContent if user_role == UserRole.GUEST else expected.no_content
    )
    if not error:
        # now wait for it to stop
        _assert_sleeper_services_completed(
            project_id, postgres_session, StateType.ABORTED, mock_workbench_payload
        )
