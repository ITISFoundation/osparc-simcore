# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import json
import sys
import time
from pathlib import Path
from pprint import pprint
from typing import Dict

import pytest
import sqlalchemy as sa
from aiohttp import web
from yarl import URL

from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser
from pytest_simcore.helpers.utils_projects import NewProject
from servicelib.application import create_safe_application
from servicelib.application_keys import APP_CONFIG_KEY
from simcore_postgres_database.webserver_models import (
    NodeClass,
    StateType,
    comp_pipeline,
    comp_tasks,
)
from simcore_service_webserver.computation import setup_computation
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

API_VERSION = "v0"
API_PREFIX = "/" + API_VERSION

# TODO: create conftest at computation/ folder level

# Selection of core and tool services started in this swarm fixture (integration)
core_services = ["director", "rabbit", "postgres", "sidecar", "storage", "redis"]

ops_services = [
    "minio",
]


@pytest.fixture
def client(
    loop,
    aiohttp_client,
    app_config,  ## waits until swarm with *_services are up
):
    assert app_config["rest"]["version"] == API_VERSION

    app_config["storage"]["enabled"] = False
    app_config["main"]["testing"] = True

    pprint(app_config)

    # fake config
    app = create_safe_application()
    app[APP_CONFIG_KEY] = app_config

    pprint(app_config)

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_projects(app)
    setup_computation(app)

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
def assert_db_contents(
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


def assert_sleeper_services_completed(project_id, postgres_session):
    # pylint: disable=no-member
    # we wait 15 secs before testing...
    TIMEOUT_SECONDS = 30
    start_time = time.time()
    pipeline_result = StateType.NOT_STARTED
    # while results
    time.sleep(15)
    pipeline_db = (
        postgres_session.query(comp_pipeline)
        .filter(comp_pipeline.c.project_id == project_id)
        .one()
    )
    tasks_db = (
        postgres_session.query(comp_tasks)
        .filter(
            (comp_tasks.c.project_id == project_id)
            & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
        )
        .all()
    )
    for task_db in tasks_db:
        if "sleeper" in task_db.image["name"]:
            assert task_db.state == StateType.SUCCESS


# TESTS ------------------------------------------
async def test_check_health(loop, mock_orphaned_services, docker_stack, client):
    # TODO: check health of all core_services in list above!
    resp = await client.get(API_VERSION + "/")
    data, _ = await assert_status(resp, web.HTTPOk)

    assert data["name"] == "simcore_service_webserver"
    assert data["status"] == "SERVICE_RUNNING"


@pytest.mark.parametrize(
    "user_role,expected_response",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_start_pipeline(
    rabbit_service: str,
    postgres_session: sa.orm.session.Session,
    redis_service: URL,
    simcore_services: Dict[str, URL],
    sleeper_service: Dict[str, str],
    client,
    logged_user: LoggedUser,
    user_project: NewProject,
    mock_workbench_adjacency_list: Dict,
    expected_response: web.Response,
):
    project_id = user_project["uuid"]
    mock_workbench_payload = user_project["workbench"]

    url_get_state = client.app.router["state_project"].url_for(project_id=project_id)
    assert url_get_state == URL(API_PREFIX + "/projects/{}/state".format(project_id))

    url_start = client.app.router["start_pipeline"].url_for(project_id=project_id)
    assert url_start == URL(
        API_PREFIX + "/computation/pipeline/{}:start".format(project_id)
    )

    # POST /v0/computation/pipeline/{project_id}:start
    resp = await client.post(url_start)
    data, error = await assert_status(resp, expected_response)

    if not error:
        assert "pipeline_name" in data
        assert "project_id" in data
        assert data["project_id"] == project_id

        assert_db_contents(
            project_id,
            postgres_session,
            mock_workbench_payload,
            mock_workbench_adjacency_list,
            check_outputs=False,
        )
        assert_sleeper_services_completed(project_id, postgres_session)
