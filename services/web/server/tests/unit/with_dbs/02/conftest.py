# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import contextlib
import re
from contextlib import AsyncExitStack
from copy import deepcopy
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Final
from unittest import mock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from faker import Faker
from models_library.projects_state import ProjectState
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from pydantic import parse_obj_as
from pytest import MonkeyPatch
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from pytest_simcore.helpers.utils_login import UserInfoDict
from pytest_simcore.helpers.utils_projects import NewProject, delete_all_projects
from settings_library.catalog import CatalogSettings
from simcore_service_webserver.application_settings import get_settings
from simcore_service_webserver.catalog_settings import get_plugin_settings
from simcore_service_webserver.projects.project_models import ProjectDict


@pytest.fixture
def mock_service_resources() -> ServiceResourcesDict:
    return parse_obj_as(
        ServiceResourcesDict,
        ServiceResourcesDictHelpers.Config.schema_extra["examples"][0],
    )


@pytest.fixture
def mock_service() -> dict[str, Any]:
    return {
        "name": "File Picker",
        "thumbnail": None,
        "description": "File Picker",
        "classifiers": [],
        "quality": {},
        "access_rights": {
            "1": {"execute_access": True, "write_access": False},
            "4": {"execute_access": True, "write_access": True},
        },
        "key": "simcore/services/frontend/file-picker",
        "version": "1.0.0",
        "integration-version": None,
        "type": "dynamic",
        "badges": None,
        "authors": [
            {
                "name": "Red Pandas",
                "email": "redpandas@wonderland.com",
                "affiliation": None,
            }
        ],
        "contact": "redpandas@wonderland.com",
        "inputs": {},
        "outputs": {
            "outFile": {
                "displayOrder": 0,
                "label": "File",
                "description": "Chosen File",
                "type": "data:*/*",
                "fileToKeyMap": None,
                "widget": None,
            }
        },
        "owner": "redpandas@wonderland.com",
    }


@pytest.fixture
def mock_catalog_api(
    mocker: MockerFixture,
    mock_service_resources: ServiceResourcesDict,
    mock_service: dict[str, Any],
) -> dict[str, mock.Mock]:
    return {
        "get_service_resources": mocker.patch(
            "simcore_service_webserver.projects.projects_api.catalog_client.get_service_resources",
            return_value=mock_service_resources,
            autospec=True,
        ),
        "get_service": mocker.patch(
            "simcore_service_webserver.projects.projects_api.catalog_client.get_service",
            return_value=mock_service,
            autospec=True,
        ),
    }


@pytest.fixture
async def user_project(
    client, fake_project, logged_user, tests_data_dir: Path, osparc_product_name: str
) -> AsyncIterator[ProjectDict]:
    async with NewProject(
        fake_project,
        client.app,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
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
    osparc_product_name: str,
) -> AsyncIterator[ProjectDict]:
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
        product_name=osparc_product_name,
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
    osparc_product_name: str,
) -> AsyncIterator[ProjectDict]:
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
        product_name=osparc_product_name,
        clear_all=True,
        tests_data_dir=tests_data_dir,
        as_template=True,
    ) as template_project:
        print("-----> added template project", template_project["name"])
        yield template_project
        print("<----- removed template project", template_project["name"])


@pytest.fixture
async def create_template_project(
    client,
    fake_project,
    logged_user,
    all_group: dict[str, str],
    tests_data_dir: Path,
    osparc_product_name: str,
) -> AsyncIterator[Callable[..., Awaitable[ProjectDict]]]:
    created_projects_exit_stack = contextlib.AsyncExitStack()

    async def _creator(**prj_kwargs) -> ProjectDict:
        project_data = deepcopy(fake_project)
        project_data["name"] = "Fake template"
        project_data["uuid"] = "d4d0eca3-d210-4db6-84f9-63670b07176b"
        project_data["accessRights"] = {
            str(all_group["gid"]): {"read": True, "write": False, "delete": False}
        }
        project_data |= prj_kwargs

        new_template_project = await created_projects_exit_stack.enter_async_context(
            NewProject(
                project_data,
                client.app,
                user_id=None,
                product_name=osparc_product_name,
                clear_all=True,
                tests_data_dir=tests_data_dir,
                as_template=True,
            )
        )
        print("-----> added template project", new_template_project["name"])
        return new_template_project

    yield _creator
    await created_projects_exit_stack.aclose()
    print("<---- removed all created template projects")


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


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: MonkeyPatch
) -> EnvVarsDict:
    envs_plugins = setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_RABBITMQ": "null",
        },
    )
    return app_environment | envs_plugins


@pytest.fixture
def disable_max_number_of_running_dynamic_nodes(
    app_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    monkeypatch.setenv("PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES", "0")
    return app_environment | {"PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES": "0"}


@pytest.fixture
def max_amount_of_auto_started_dyn_services(client: TestClient) -> int:
    assert client.app
    projects_settings = get_settings(client.app).WEBSERVER_PROJECTS
    assert projects_settings
    return projects_settings.PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES


@pytest.fixture
async def user_project_with_num_dynamic_services(
    client: TestClient,
    logged_user: UserInfoDict,
    tests_data_dir: Path,
    osparc_product_name: str,
    faker: Faker,
) -> AsyncIterator[Callable[[int], Awaitable[ProjectDict]]]:
    async with AsyncExitStack() as stack:

        async def _creator(num_dyn_services: int) -> ProjectDict:
            project_data = {
                "workbench": {
                    faker.uuid4(): {
                        "key": f"simcore/services/dynamic/{faker.pystr().lower()}",
                        "version": faker.numerify("#.#.#"),
                        "label": faker.name(),
                    }
                    for _ in range(num_dyn_services)
                }
            }
            project = await stack.enter_async_context(
                NewProject(
                    project_data,
                    client.app,
                    user_id=logged_user["id"],
                    product_name=osparc_product_name,
                    tests_data_dir=tests_data_dir,
                )
            )
            print("-----> added project", project["name"])
            assert "workbench" in project
            dynamic_services = list(
                filter(
                    lambda service: "/dynamic/" in service["key"],
                    project["workbench"].values(),
                )
            )
            assert len(dynamic_services) == num_dyn_services

            return project

        yield _creator
    print("<----- cleaned up projects")


@pytest.fixture
def mock_catalog_service_api_responses(client, aioresponses_mocker):
    settings: CatalogSettings = get_plugin_settings(client.app)
    url_pattern = re.compile(f"^{settings.base_url}+/.*$")

    aioresponses_mocker.get(
        url_pattern,
        payload={"data": {}},
        repeat=True,
    )
    aioresponses_mocker.post(
        url_pattern,
        payload={"data": {}},
        repeat=True,
    )
    aioresponses_mocker.put(
        url_pattern,
        payload={"data": {}},
        repeat=True,
    )
    aioresponses_mocker.patch(
        url_pattern,
        payload={"data": {}},
        repeat=True,
    )
    aioresponses_mocker.delete(
        url_pattern,
        repeat=True,
    )


@pytest.fixture
def mock_get_total_project_dynamic_nodes_creation_interval(
    mocker: MockerFixture,
) -> None:
    _VERY_LONG_LOCK_TIMEOUT_S: Final[float] = 300
    mocker.patch(
        "simcore_service_webserver.projects.projects_api._nodes_utils"
        ".get_total_project_dynamic_nodes_creation_interval",
        return_value=_VERY_LONG_LOCK_TIMEOUT_S,
    )
