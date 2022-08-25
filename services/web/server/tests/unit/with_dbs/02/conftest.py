# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from copy import deepcopy
from pathlib import Path
from typing import Any, AsyncIterable, AsyncIterator, Callable, Optional, Union

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
from simcore_service_webserver import catalog
from simcore_service_webserver.application import create_application

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
    cfg["statics"]["enabled"] = False

    monkeypatch_setenv_from_app_config(cfg)
    app = create_application()

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
