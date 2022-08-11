# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from copy import deepcopy
from pathlib import Path
from typing import (
    Any,
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Callable,
    Optional,
    Union,
)

import pytest
from aiohttp import web
from aioresponses import aioresponses
from models_library.projects_access import Owner
from models_library.projects_state import (
    ProjectLocked,
    ProjectRunningState,
    ProjectState,
    ProjectStatus,
    RunningState,
)
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from pydantic import parse_obj_as
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_projects import NewProject, delete_all_projects
from servicelib.aiohttp.application import create_safe_application
from servicelib.aiohttp.long_running_tasks.server import TaskResult, TaskStatus
from servicelib.aiohttp.long_running_tasks.server import (
    setup as setup_long_running_tasks,
)
from simcore_service_webserver import catalog
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.director.plugin import setup_director
from simcore_service_webserver.director_v2 import setup_director_v2
from simcore_service_webserver.garbage_collector import setup_garbage_collector
from simcore_service_webserver.login.plugin import setup_login
from simcore_service_webserver.products import setup_products
from simcore_service_webserver.projects.plugin import setup_projects
from simcore_service_webserver.projects.project_models import ProjectDict
from simcore_service_webserver.projects.projects_handlers_crud import (
    OVERRIDABLE_DOCUMENT_KEYS,
)
from simcore_service_webserver.resource_manager.plugin import setup_resource_manager
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio.plugin import setup_socketio
from simcore_service_webserver.tags import setup_tags
from simcore_service_webserver.utils import now_str, to_datetime
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL

DEFAULT_GARBAGE_COLLECTOR_INTERVAL_SECONDS: int = 3
DEFAULT_GARBAGE_COLLECTOR_DELETION_TIMEOUT_SECONDS: int = 3


@pytest.fixture
def client(
    event_loop,
    aiohttp_client,
    app_cfg,
    postgres_db,
    mocked_director_v2_api,
    mock_orphaned_services,
    mock_catalog_api: None,
    redis_client,
    monkeypatch_setenv_from_app_config: Callable,
):

    # config app
    cfg = deepcopy(app_cfg)
    port = cfg["main"]["port"]
    cfg["projects"]["enabled"] = True
    cfg["director"]["enabled"] = True
    cfg["resource_manager"][
        "garbage_collection_interval_seconds"
    ] = DEFAULT_GARBAGE_COLLECTOR_INTERVAL_SECONDS  # increase speed of garbage collection
    cfg["resource_manager"][
        "resource_deletion_timeout_seconds"
    ] = DEFAULT_GARBAGE_COLLECTOR_DELETION_TIMEOUT_SECONDS  # reduce deletion delay

    monkeypatch_setenv_from_app_config(cfg)
    app = create_safe_application(cfg)

    # setup app

    assert setup_settings(app)
    setup_long_running_tasks(app, router_prefix="/tasks")
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)  # needed for login_utils fixtures
    setup_resource_manager(app)
    setup_garbage_collector(app)
    setup_socketio(app)
    setup_director(app)
    setup_director_v2(app)
    setup_tags(app)
    assert setup_projects(app)
    setup_products(app)

    # server and client
    yield event_loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"port": port, "host": "localhost"})
    )

    # teardown here ...


@pytest.fixture
def mocks_on_projects_api(mocker, logged_user) -> None:
    """
    All projects in this module are UNLOCKED

    Emulates that it found logged_user as the SOLE user of this project
    and returns the  ProjectState indicating his as owner
    """
    nameparts = logged_user["name"].split(".") + [""]
    state = ProjectState(
        locked=ProjectLocked(
            value=False,
            owner=Owner(
                user_id=logged_user["id"],
                first_name=nameparts[0],
                last_name=nameparts[1],
            ),
            status=ProjectStatus.CLOSED,
        ),
        state=ProjectRunningState(value=RunningState.NOT_STARTED),
    )
    mocker.patch(
        "simcore_service_webserver.projects.projects_api._get_project_lock_state",
        return_value=state,
    )


@pytest.fixture
def mock_service_resources() -> ServiceResourcesDict:
    return parse_obj_as(
        ServiceResourcesDict,
        ServiceResourcesDictHelpers.Config.schema_extra["examples"][0],
    )


@pytest.fixture
def mock_catalog_api(mocker, mock_service_resources: ServiceResourcesDict) -> None:
    mocker.patch(
        "simcore_service_webserver.catalog_client.get_service_resources",
        return_value=mock_service_resources,
    )


@pytest.fixture
async def user_project(
    client,
    fake_project,
    logged_user,
    tests_data_dir: Path,
):
    async with NewProject(
        fake_project,
        client.app,
        user_id=logged_user["id"],
        tests_data_dir=tests_data_dir,
    ) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])


@pytest.fixture
async def shared_project(
    client,
    fake_project,
    logged_user,
    all_group,
    tests_data_dir: Path,
):
    fake_project.update(
        {
            "accessRights": {
                f"{all_group['gid']}": {"read": True, "write": False, "delete": False}
            },
        },
    )
    async with NewProject(
        fake_project,
        client.app,
        user_id=logged_user["id"],
        tests_data_dir=tests_data_dir,
    ) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])


@pytest.fixture
async def template_project(
    client,
    fake_project,
    logged_user,
    all_group: dict[str, str],
    tests_data_dir: Path,
) -> AsyncIterable[dict[str, Any]]:
    project_data = deepcopy(fake_project)
    project_data["name"] = "Fake template"
    project_data["uuid"] = "d4d0eca3-d210-4db6-84f9-63670b07176b"
    project_data["accessRights"] = {
        str(all_group["gid"]): {"read": True, "write": False, "delete": False}
    }

    async with NewProject(
        project_data,
        client.app,
        user_id=None,
        clear_all=True,
        tests_data_dir=tests_data_dir,
    ) as template_project:
        print("-----> added template project", template_project["name"])
        yield template_project
        print("<----- removed template project", template_project["name"])


@pytest.fixture
def fake_services():
    def create_fakes(number_services: int) -> list[dict]:
        fake_services = [{"service_uuid": f"{i}_uuid"} for i in range(number_services)]
        return fake_services

    yield create_fakes


@pytest.fixture
async def project_db_cleaner(client):
    yield
    await delete_all_projects(client.app)


@pytest.fixture
async def catalog_subsystem_mock(
    monkeypatch,
) -> Callable[[Optional[Union[list[dict], dict]]], None]:
    services_in_project = []

    def creator(projects: Optional[Union[list[dict], dict]] = None) -> None:
        for proj in projects or []:
            services_in_project.extend(
                [
                    {"key": s["key"], "version": s["version"]}
                    for _, s in proj["workbench"].items()
                ]
            )

    async def mocked_get_services_for_user(*args, **kwargs):
        return services_in_project

    monkeypatch.setattr(
        catalog, "get_services_for_user_in_product", mocked_get_services_for_user
    )

    return creator


@pytest.fixture(autouse=True)
async def mocked_director_v2(
    director_v2_service_mock: aioresponses,
) -> AsyncIterator[aioresponses]:
    yield director_v2_service_mock


@pytest.fixture()
def assert_get_same_project_caller() -> Callable:
    async def _assert_it(
        client,
        project: dict,
        expected: type[web.HTTPException],
    ) -> dict:
        # GET /v0/projects/{project_id} with a project owned by user
        url = client.app.router["get_project"].url_for(project_id=project["uuid"])
        resp = await client.get(url)
        data, error = await assert_status(resp, expected)

        if not error:
            project_state = data.pop("state")
            assert data == project
            assert ProjectState(**project_state)
        return data

    return _assert_it


def _minimal_project() -> ProjectDict:
    return {
        "uuid": "0000000-invalid-uuid",
        "name": "Minimal name",
        "description": "this description should not change",
        "prjOwner": "me but I will be removed anyway",
        "creationDate": now_str(),
        "lastChangeDate": now_str(),
        "thumbnail": "",
        "accessRights": {},
        "workbench": {},
        "tags": [],
        "classifiers": [],
        "ui": {},
        "dev": {},
        "quality": {},
    }


@pytest.fixture
def create_project() -> Callable[..., Awaitable[ProjectDict]]:
    async def _creator(
        client,
        expected_response: type[web.HTTPException],
        logged_user: dict[str, str],
        primary_group: dict[str, str],
        *,
        project: Optional[dict] = None,
        from_study: Optional[dict] = None,
        as_template: Optional[bool] = None,
    ) -> ProjectDict:
        # Pre-defined fields imposed by required properties in schema
        project_data = {}
        expected_data = {}
        if from_study:
            # access rights are replaced
            expected_data = deepcopy(from_study)
            expected_data["accessRights"] = {}
            if not as_template:
                expected_data["name"] = f"{from_study['name']} (Copy)"
        if not from_study or project:
            project_data = _minimal_project()
            if project:
                project_data.update(project)
            for key in project_data:
                expected_data[key] = project_data[key]
                if (
                    key in OVERRIDABLE_DOCUMENT_KEYS
                    and not project_data[key]
                    and from_study
                ):
                    expected_data[key] = from_study[key]

        # POST /v0/projects -> returns 202
        url: URL = client.app.router["create_projects"].url_for()
        if from_study:
            url = url.update_query(from_study=from_study["uuid"])
        if as_template:
            url = url.update_query(as_template=f"{as_template}")
        resp = await client.post(url, json=project_data)
        print(f"<-- created project response: {resp=}")
        data, error = await assert_status(resp, expected_response)
        if error:
            assert not data
            return {}
        assert data
        assert all(x in data for x in ["task_id", "status_href", "result_href"])
        assert "Location" in resp.headers
        status_url = resp.headers.get("location")
        assert status_url == data["status_href"]
        result_url = data["result_href"]

        # get status GET /{task_id}
        async for attempt in AsyncRetrying(
            wait=wait_fixed(0.1),
            stop=stop_after_delay(60),
            reraise=True,
            retry=retry_if_exception_type(AssertionError),
        ):
            with attempt:
                print(
                    f"--> waiting for creation {attempt.retry_state.attempt_number}..."
                )
                result = await client.get(f"{status_url}")
                data, error = await assert_status(result, web.HTTPOk)
                assert data
                assert not error
                task_status = TaskStatus.parse_obj(data)
                assert task_status
                print(f"<-- status: {task_status.json(indent=2)}")
                assert task_status.done, "task incomplete"
                print(
                    f"-- project creation completed: {json.dumps(attempt.retry_state.retry_object.statistics, indent=2)}"
                )

        # get result GET /{task_id}/result
        print(f"--> getting project creation result...")
        result = await client.get(f"{result_url}")
        data, error = await assert_status(result, web.HTTPOk)
        assert data
        assert not error
        task_result = TaskResult.parse_obj(data)
        print(f"<-- result: {task_result.json(indent=2)}")
        assert not task_result.error
        assert task_result.result
        new_project = task_result.result

        # now check returned is as expected
        if new_project:
            # has project state
            assert not ProjectState(
                **new_project.get("state", {})
            ).locked.value, "Newly created projects should be unlocked"

            # updated fields
            assert expected_data["uuid"] != new_project["uuid"]
            assert (
                new_project["prjOwner"] == logged_user["email"]
            )  # the project owner is assigned the user id e-mail
            assert to_datetime(expected_data["creationDate"]) < to_datetime(
                new_project["creationDate"]
            )
            assert to_datetime(expected_data["lastChangeDate"]) < to_datetime(
                new_project["lastChangeDate"]
            )
            # the access rights are set to use the logged user primary group + whatever was inside the project
            expected_data["accessRights"].update(
                {
                    str(primary_group["gid"]): {
                        "read": True,
                        "write": True,
                        "delete": True,
                    }
                }
            )
            assert new_project["accessRights"] == expected_data["accessRights"]

            # invariant fields
            modified_fields = [
                "uuid",
                "prjOwner",
                "creationDate",
                "lastChangeDate",
                "accessRights",
                "workbench" if from_study else None,
                "ui" if from_study else None,
                "state",
            ]

            for key in new_project.keys():
                if key not in modified_fields:
                    assert expected_data[key] == new_project[key]

        return new_project

    return _creator
