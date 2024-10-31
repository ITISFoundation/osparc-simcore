# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import contextlib
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack
from copy import deepcopy
from http import HTTPStatus
from pathlib import Path
from typing import Any, Final
from unittest import mock

import pytest
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from faker import Faker
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.projects_nodes import Node, NodeID
from models_library.projects_state import ProjectState
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_projects import NewProject, delete_all_projects
from settings_library.catalog import CatalogSettings
from simcore_service_webserver.application_settings import get_application_settings
from simcore_service_webserver.catalog.settings import get_plugin_settings
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def mock_service_resources() -> ServiceResourcesDict:
    return TypeAdapter(ServiceResourcesDict).validate_python(
        ServiceResourcesDictHelpers.model_config["json_schema_extra"]["examples"][0],
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
    client: TestClient,
    fake_project,
    logged_user,
    tests_data_dir: Path,
    osparc_product_name: str,
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
    user: UserInfoDict,
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
        user_id=user["id"],
        product_name=osparc_product_name,
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
    user: UserInfoDict,
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
                user_id=user["id"],
                product_name=osparc_product_name,
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
def fake_services(
    create_dynamic_service_mock: Callable[..., Awaitable[DynamicServiceGet]]
) -> Callable[..., Awaitable[list[DynamicServiceGet]]]:
    async def create_fakes(number_services: int) -> list[DynamicServiceGet]:
        return [await create_dynamic_service_mock() for _ in range(number_services)]

    return create_fakes


@pytest.fixture
async def project_db_cleaner(client: TestClient):
    assert client.app
    yield
    await delete_all_projects(client.app)


@pytest.fixture(autouse=True)
async def mocked_director_v2(
    director_v2_service_mock: aioresponses,
) -> AsyncIterator[aioresponses]:
    return director_v2_service_mock


@pytest.fixture()
def assert_get_same_project_caller() -> Callable:
    async def _assert_it(
        client,
        project: dict,
        expected: HTTPStatus,
    ) -> dict:
        # GET /v0/projects/{project_id} with a project owned by user
        url = client.app.router["get_project"].url_for(project_id=project["uuid"])
        resp = await client.get(f"{url}")
        data, error = await assert_status(resp, expected)

        if not error:
            project_state = data.pop("state")
            assert data == project
            assert ProjectState(**project_state)
        return data

    return _assert_it


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    envs_plugins = setenvs_from_dict(
        monkeypatch,
        {},
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
    projects_settings = get_application_settings(client.app).WEBSERVER_PROJECTS
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
        "simcore_service_webserver.projects.projects_api._nodes_api"
        ".get_total_project_dynamic_nodes_creation_interval",
        return_value=_VERY_LONG_LOCK_TIMEOUT_S,
    )


@pytest.fixture
def workbench_db_column() -> dict[str, Any]:
    return {
        "13220a1d-a569-49de-b375-904301af9295": {
            "key": "simcore/services/comp/itis/sleeper",
            "version": "2.1.4",
            "label": "sleeper",
            "inputs": {
                "input_2": {
                    "nodeUuid": "38a0d401-af4b-4ea7-ab4c-5005c712a546",
                    "output": "out_1",
                },
                "input_3": False,
                "input_4": 0,
            },
            "inputsUnits": {},
            "inputNodes": ["38a0d401-af4b-4ea7-ab4c-5005c712a546"],
            "parent": None,
            "thumbnail": "",
        },
        "38a0d401-af4b-4ea7-ab4c-5005c712a546": {
            "key": "simcore/services/frontend/parameter/integer",
            "version": "1.0.0",
            "label": "X",
            "inputs": {},
            "inputsUnits": {},
            "inputNodes": [],
            "parent": None,
            "thumbnail": "",
            "outputs": {"out_1": 43},
            "runHash": None,
        },
        "08d15a6c-ae7b-4ea1-938e-4ce81a360ffa": {
            "key": "simcore/services/comp/itis/sleeper",
            "version": "2.1.4",
            "label": "sleeper_2",
            "inputs": {
                "input_2": 2,
                "input_3": {
                    "nodeUuid": "7bf0741f-bae4-410b-b662-fc34b47c27c9",
                    "output": "out_1",
                },
                "input_4": {
                    "nodeUuid": "fc48252a-9dbb-4e07-bf9a-7af65a18f612",
                    "output": "out_1",
                },
            },
            "inputsUnits": {},
            "inputNodes": [
                "fc48252a-9dbb-4e07-bf9a-7af65a18f612",
                "7bf0741f-bae4-410b-b662-fc34b47c27c9",
            ],
            "parent": None,
            "thumbnail": "",
            "state": {"currentStatus": "SUCCESS"},
            "progress": 100,
            "outputs": {
                "output_1": {
                    "store": 0,
                    "path": "e08316a8-5afc-11ed-bab7-02420a00002b/08d15a6c-ae7b-4ea1-938e-4ce81a360ffa/single_number.txt",
                    "eTag": "1679091c5a880faf6fb5e6087eb1b2dc",
                },
                "output_2": 6,
            },
            "runHash": "5d55ebe569aa0abeb5287104dc5989eabc755f160c9a5c9a1cc783fe1e058b66",
        },
        "fc48252a-9dbb-4e07-bf9a-7af65a18f612": {
            "key": "simcore/services/frontend/parameter/integer",
            "version": "1.0.0",
            "label": "Z",
            "inputs": {},
            "inputsUnits": {},
            "inputNodes": [],
            "parent": None,
            "thumbnail": "",
            "outputs": {"out_1": 1},
            "runHash": None,
        },
        "7bf0741f-bae4-410b-b662-fc34b47c27c9": {
            "key": "simcore/services/frontend/parameter/boolean",
            "version": "1.0.0",
            "label": "on",
            "inputs": {},
            "inputsUnits": {},
            "inputNodes": [],
            "parent": None,
            "thumbnail": "",
            "outputs": {"out_1": False},
            "runHash": None,
        },
        "09fd512e-0768-44ca-81fa-0cecab74ec1a": {
            "key": "simcore/services/frontend/iterator-consumer/probe/integer",
            "version": "1.0.0",
            "label": "Random sleep interval_2",
            "inputs": {
                "in_1": {
                    "nodeUuid": "13220a1d-a569-49de-b375-904301af9295",
                    "output": "output_2",
                }
            },
            "inputsUnits": {},
            "inputNodes": ["13220a1d-a569-49de-b375-904301af9295"],
            "parent": None,
            "thumbnail": "",
        },
        "76f607b4-8761-4f96-824d-cab670bc45f5": {
            "key": "simcore/services/frontend/iterator-consumer/probe/integer",
            "version": "1.0.0",
            "label": "Random sleep interval",
            "inputs": {
                "in_1": {
                    "nodeUuid": "08d15a6c-ae7b-4ea1-938e-4ce81a360ffa",
                    "output": "output_2",
                }
            },
            "inputsUnits": {},
            "inputNodes": ["08d15a6c-ae7b-4ea1-938e-4ce81a360ffa"],
            "parent": None,
            "thumbnail": "",
        },
    }


@pytest.fixture
def workbench(workbench_db_column: dict[str, Any]) -> dict[NodeID, Node]:
    # convert to  model
    return TypeAdapter(dict[NodeID, Node]).validate_python(workbench_db_column)
