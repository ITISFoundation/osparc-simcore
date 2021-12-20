# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
import asyncio
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Tuple, Type, Union

import pytest
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.projects_state import RunningState
from models_library.settings.rabbit import RabbitConfig
from models_library.settings.redis import RedisConfig
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.aiohttp.application import create_safe_application
from servicelib.json_serialization import json_dumps
from simcore_postgres_database.webserver_models import (
    NodeClass,
    StateType,
    comp_pipeline,
    comp_tasks,
)
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.computation import setup_computation
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.diagnostics import setup_diagnostics
from simcore_service_webserver.director_v2 import setup_director_v2
from simcore_service_webserver.login.module_setup import setup_login
from simcore_service_webserver.projects.module_setup import setup_projects
from simcore_service_webserver.resource_manager.module_setup import (
    setup_resource_manager,
)
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio.module_setup import setup_socketio
from simcore_service_webserver.users import setup_users
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL

API_VTAG = "v0"
API_PREFIX = "/" + API_VTAG


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


class ExpectedResponse(NamedTuple):
    """
    Stores respons status to an API request in function of the user

    e.g. for a request that normally returns OK, a non-authorized user
    will have no access, therefore ExpectedResponse.ok = HTTPUnauthorized
    """

    ok: Union[Type[web.HTTPUnauthorized], Type[web.HTTPForbidden], Type[web.HTTPOk]]
    created: Union[
        Type[web.HTTPUnauthorized], Type[web.HTTPForbidden], Type[web.HTTPCreated]
    ]
    no_content: Union[
        Type[web.HTTPUnauthorized], Type[web.HTTPForbidden], Type[web.HTTPNoContent]
    ]
    forbidden: Union[
        Type[web.HTTPUnauthorized],
        Type[web.HTTPForbidden],
    ]

    def __str__(self) -> str:
        items = ", ".join(  # pylint: disable=no-member
            f"{k}={v.__name__}" for k, v in self._asdict().items()
        )
        return f"{self.__class__.__name__}({items})"


def standard_role_response() -> Tuple[str, List[Tuple[UserRole, ExpectedResponse]]]:
    return (
        "user_role,expected",
        [
            (
                UserRole.ANONYMOUS,
                ExpectedResponse(
                    ok=web.HTTPUnauthorized,
                    created=web.HTTPUnauthorized,
                    no_content=web.HTTPUnauthorized,
                    forbidden=web.HTTPUnauthorized,
                ),
            ),
            (
                UserRole.GUEST,
                ExpectedResponse(
                    ok=web.HTTPOk,
                    created=web.HTTPCreated,
                    no_content=web.HTTPNoContent,
                    forbidden=web.HTTPForbidden,
                ),
            ),
            (
                UserRole.USER,
                ExpectedResponse(
                    ok=web.HTTPOk,
                    created=web.HTTPCreated,
                    no_content=web.HTTPNoContent,
                    forbidden=web.HTTPForbidden,
                ),
            ),
            (
                UserRole.TESTER,
                ExpectedResponse(
                    ok=web.HTTPOk,
                    created=web.HTTPCreated,
                    no_content=web.HTTPNoContent,
                    forbidden=web.HTTPForbidden,
                ),
            ),
        ],
    )


# FIXTURES ----------------------------------------------------------------------------


@pytest.fixture
def client(
    loop: asyncio.AbstractEventLoop,
    postgres_session: sa.orm.session.Session,
    rabbit_service: RabbitConfig,
    redis_service: RedisConfig,
    simcore_services_ready: None,
    aiohttp_client: Callable,
    app_config: Dict[str, Any],  ## waits until swarm with *_services are up
    mocker: MockerFixture,
) -> TestClient:
    assert app_config["rest"]["version"] == API_VTAG

    app_config["storage"]["enabled"] = False
    app_config["main"]["testing"] = True

    # fake config
    app = create_safe_application(app_config)

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_diagnostics(app)
    setup_login(app)
    setup_users(app)
    setup_socketio(app)
    setup_projects(app)
    setup_computation(app)
    setup_director_v2(app)

    # GC not included in this test-suite,
    mocker.patch(
        "simcore_service_webserver.resource_manager.module_setup.setup_garbage_collector",
        side_effect=lambda app: print(
            f"PATCH @{__name__}:"
            "Garbage collector disabled."
            "Mock bypasses setup_garbage_collector to skip initializing the GC"
        ),
    )
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
def fake_workbench_adjacency_list(tests_data_dir: Path) -> Dict[str, Any]:
    file_path = tests_data_dir / "workbench_sleeper_dag_adjacency_list.json"
    with file_path.open() as fp:
        return json.load(fp)


# HELPERS ----------------------------------
def _assert_db_contents(
    project_id: str,
    postgres_session: sa.orm.session.Session,
    fake_workbench_payload: Dict[str, Any],
    fake_workbench_adjacency_list: Dict[str, Any],
    check_outputs: bool,
):
    # pylint: disable=no-member
    pipeline_db = (
        postgres_session.query(comp_pipeline)
        .filter(comp_pipeline.c.project_id == project_id)
        .one()
    )
    assert pipeline_db.project_id == project_id
    assert pipeline_db.dag_adjacency_list == fake_workbench_adjacency_list

    # check db comp_tasks
    tasks_db = (
        postgres_session.query(comp_tasks)
        .filter(comp_tasks.c.project_id == project_id)
        .all()
    )
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


async def _assert_sleeper_services_completed(
    project_id: str,
    postgres_session: sa.orm.session.Session,
    expected_state: StateType,
    fake_workbench_payload: Dict[str, Any],
):
    NUM_COMP_TASKS_TO_WAIT_FOR = len(
        [x for x in fake_workbench_payload.values() if "/comp/" in x["key"]]
    )

    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_delay(120),
        wait=wait_fixed(5),
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            print(
                f"--> waiting for pipeline to complete attempt {attempt.retry_state.attempt_number}..."
            )
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
            print(f"--> tasks from DB: {tasks_db=}")
            assert (
                len(tasks_db) == NUM_COMP_TASKS_TO_WAIT_FOR
            ), f"all tasks have not finished, expected {NUM_COMP_TASKS_TO_WAIT_FOR}, got {len(tasks_db)}"
            # get the different states in a set of states
            set_of_states = {task_db.state for task_db in tasks_db}
            print(f"--> states found: {set_of_states=}")
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
            print(
                f"--> pipeline completed! That's great: {json_dumps(attempt.retry_state.retry_object.statistics)}",
            )


# TESTS ------------------------------------------
@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_start_stop_pipeline(
    client: TestClient,
    sleeper_service: Dict[str, str],
    postgres_session: sa.orm.session.Session,
    logged_user: Dict[str, Any],
    user_project: Dict[str, Any],
    fake_workbench_adjacency_list: Dict[str, Any],
    user_role: UserRole,
    expected: ExpectedResponse,
):
    project_id = user_project["uuid"]
    fake_workbench_payload = user_project["workbench"]

    url_start = client.app.router["start_pipeline"].url_for(project_id=project_id)
    assert url_start == URL(f"/{API_VTAG}/computation/pipeline/{project_id}:start")

    # POST /v0/computation/pipeline/{project_id}:start
    resp = await client.post(f"{url_start}")
    data, error = await assert_status(resp, expected.created)

    if not error:
        # starting again should be disallowed, since it's already running
        resp = await client.post(f"{url_start}")
        assert resp.status == expected.forbidden.status_code

        assert "pipeline_id" in data
        assert data["pipeline_id"] == project_id

        _assert_db_contents(
            project_id,
            postgres_session,
            fake_workbench_payload,
            fake_workbench_adjacency_list,
            check_outputs=False,
        )
        # wait for the computation to stop
        await _assert_sleeper_services_completed(
            project_id, postgres_session, StateType.SUCCESS, fake_workbench_payload
        )
        # restart the computation, this should produce a 422 since the computation was complete
        resp = await client.post(f"{url_start}")
        assert resp.status == web.HTTPUnprocessableEntity.status_code
        # force restart the computation
        resp = await client.post(f"{url_start}", json={"force_restart": True})
        data, error = await assert_status(resp, expected.created)
        assert not error

    # give time to run a bit ... before stoppinng
    await asyncio.sleep(2)

    # now stop the pipeline
    # POST /v0/computation/pipeline/{project_id}:stop
    url_stop = client.app.router["stop_pipeline"].url_for(project_id=project_id)
    assert url_stop == URL(f"/{API_VTAG}/computation/pipeline/{project_id}:stop")
    resp = await client.post(f"{url_stop}")
    data, error = await assert_status(resp, expected.no_content)
    if not error:
        # now wait for it to stop
        await _assert_sleeper_services_completed(
            project_id, postgres_session, StateType.ABORTED, fake_workbench_payload
        )
        # leave some time for properly stopping the tasks
        await asyncio.sleep(10)


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_run_pipeline_and_check_state(
    client: TestClient,
    sleeper_service: Dict[str, str],
    postgres_session: sa.orm.session.Session,
    logged_user: Dict[str, Any],
    user_project: Dict[str, Any],
    fake_workbench_adjacency_list: Dict[str, Any],
    user_role: UserRole,
    expected: ExpectedResponse,
):
    project_id = user_project["uuid"]
    fake_workbench_payload = user_project["workbench"]

    url_start = client.app.router["start_pipeline"].url_for(project_id=project_id)
    assert url_start == URL(f"/{API_VTAG}/computation/pipeline/{project_id}:start")

    # POST /v0/computation/pipeline/{project_id}:start
    resp = await client.post(f"{url_start}")
    data, error = await assert_status(resp, expected.created)

    if error:
        return

    assert "pipeline_id" in data
    assert data["pipeline_id"] == project_id

    _assert_db_contents(
        project_id,
        postgres_session,
        fake_workbench_payload,
        fake_workbench_adjacency_list,
        check_outputs=False,
    )

    url_project_state = client.app.router["state_project"].url_for(
        project_id=project_id
    )
    assert url_project_state == URL(f"/{API_VTAG}/projects/{project_id}/state")

    running_state_order_lookup = {
        RunningState.UNKNOWN: 0,
        RunningState.NOT_STARTED: 1,
        RunningState.PUBLISHED: 2,
        RunningState.PENDING: 3,
        RunningState.STARTED: 4,
        RunningState.RETRY: 5,
        RunningState.SUCCESS: 6,
        RunningState.FAILED: 6,
        RunningState.ABORTED: 6,
    }

    assert all(  # pylint: disable=use-a-generator
        [k in running_state_order_lookup for k in RunningState.__members__]
    ), "there are missing members in the order lookup, please complete!"

    pipeline_state = RunningState.UNKNOWN

    start = time.monotonic()
    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_delay(120),
        wait=wait_fixed(0.1),
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
    assert pipeline_state == RunningState.SUCCESS
    print(f"<-- pipeline completed successfully in {time.monotonic() - start} seconds")
