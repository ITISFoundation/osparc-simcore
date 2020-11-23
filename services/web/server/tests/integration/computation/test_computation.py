# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import asyncio
import json
import sys
from pathlib import Path
from typing import Callable, Dict
from aiohttp.web_exceptions import HTTPCreated

import pytest
import sqlalchemy as sa
from aiohttp import web
from socketio.exceptions import ConnectionError as SocketConnectionError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed
from yarl import URL


from _helpers import ExpectedResponse, standard_role_response
from models_library.settings.rabbit import RabbitConfig
from models_library.settings.redis import RedisConfig
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser
from pytest_simcore.helpers.utils_projects import NewProject
from servicelib.application import create_safe_application
from simcore_postgres_database.webserver_models import (
    NodeClass,
    StateType,
    comp_pipeline,
    comp_tasks,
)
from simcore_service_webserver.computation import setup_computation
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.director_v2 import setup_director_v2
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.resource_manager import setup_resource_manager
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio import setup_socketio
from simcore_service_webserver.users import setup_users

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

API_VERSION = "v0"
API_PREFIX = "/" + API_VERSION

# Selection of core and tool services started in this swarm fixture (integration)
core_services = [
    "redis",
    "rabbit",
    "director",
    "director-v2",
    "postgres",
    "sidecar",
    "storage",
]

ops_services = ["minio", "adminer"]


@pytest.fixture
def client(
    loop,
    aiohttp_client,
    app_config,  ## waits until swarm with *_services are up
):
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

    yield loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={
                "port": app_config["main"]["port"],
                "host": app_config["main"]["host"],
            },
        )
    )


@pytest.fixture(scope="session")
def mock_workbench_adjacency_list() -> Dict:
    file_path = current_dir / "workbench_sleeper_dag_adjacency_list.json"
    with file_path.open() as fp:
        return json.load(fp)


# HELPERS ----------------------------------
def _assert_db_contents(
    project_id,
    postgres_session,
    mock_workbench_payload,
    mock_workbench_adjacency_list,
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
    mock_workbench_payload,
):
    # pylint: disable=no-member
    TIMEOUT_SECONDS = 60
    WAIT_TIME = 1
    NUM_COMP_TASKS_TO_WAIT_FOR = len(
        [x for x in mock_workbench_payload.values() if "/comp/" in x["key"]]
    )

    @retry(
        reraise=True,
        stop=stop_after_attempt(TIMEOUT_SECONDS / WAIT_TIME),
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
    simcore_services: Dict[str, URL],
    client,
    client_session_id: str,
    socketio_client: Callable,
    logged_user: LoggedUser,
    user_project: NewProject,
    mock_workbench_adjacency_list: Dict,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    project_id = user_project["uuid"]
    mock_workbench_payload = user_project["workbench"]
    # connect websocket (to prevent the GC to remove the project)
    try:
        sio = await socketio_client(client_session_id)
        assert sio.sid
    except SocketConnectionError:
        if expected.created == web.HTTPCreated:
            pytest.fail("socket io connection should not fail")

    url_start = client.app.router["start_pipeline"].url_for(project_id=project_id)
    assert url_start == URL(
        API_PREFIX + "/computation/pipeline/{}:start".format(project_id)
    )

    # POST /v0/computation/pipeline/{project_id}:start
    resp = await client.post(url_start)
    data, error = await assert_status(
        resp, web.HTTPCreated if user_role == UserRole.GUEST else expected.created
    )

    if not error:
        # starting again should be disallowed
        resp = await client.post(url_start)
        assert (
            resp.status == web.HTTPForbidden.status_code
            if user_role == UserRole.GUEST
            else expected.forbidden.status_code
        )
        # FIXME: to PC: I have an issue here with how the webserver middleware transforms errors (see director_v2.py)
        # await assert_status(
        #     resp,
        #     web.HTTPForbidden if user_role == UserRole.GUEST else expected.forbidden,
        # )

        assert "pipeline_id" in data
        assert data["pipeline_id"] == project_id

        _assert_db_contents(
            project_id,
            postgres_session,
            mock_workbench_payload,
            mock_workbench_adjacency_list,
            check_outputs=False,
        )
        _assert_sleeper_services_completed(
            project_id, postgres_session, StateType.SUCCESS, mock_workbench_payload
        )
        resp = await client.post(url_start)
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
    resp = await client.post(url_stop)
    data, error = await assert_status(
        resp, web.HTTPNoContent if user_role == UserRole.GUEST else expected.no_content
    )
    if not error:
        _assert_sleeper_services_completed(
            project_id, postgres_session, StateType.ABORTED, mock_workbench_payload
        )
