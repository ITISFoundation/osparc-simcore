# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from faker import Faker
from models_library.products import ProductName
from models_library.projects import ProjectID
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_projects import NewProject
from pytest_simcore.helpers.webserver_users import NewUser, UserInfoDict
from servicelib.rabbitmq.rpc_interfaces.webserver.errors import (
    ProjectForbiddenRpcError,
    ProjectNotFoundRpcError,
)
from servicelib.rabbitmq.rpc_interfaces.webserver.v1 import WebServerRpcClient
from settings_library.rabbit import RabbitSettings
from simcore_service_webserver.application_settings import ApplicationSettings
from simcore_service_webserver.projects._metadata_service import (
    set_project_custom_metadata,
)
from simcore_service_webserver.projects.models import ProjectDict

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture(scope="session")
def service_name() -> str:
    return "wb-api-server"


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


@pytest.fixture
def app_environment(
    rabbit_service: RabbitSettings,
    app_environment: EnvVarsDict,
    docker_compose_service_environment_dict: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
):
    new_envs = setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_environment_dict,
            **app_environment,
            "RABBIT_HOST": rabbit_service.RABBIT_HOST,
            "RABBIT_PORT": f"{rabbit_service.RABBIT_PORT}",
            "RABBIT_USER": rabbit_service.RABBIT_USER,
            "RABBIT_SECURE": f"{rabbit_service.RABBIT_SECURE}",
            "RABBIT_PASSWORD": rabbit_service.RABBIT_PASSWORD.get_secret_value(),
        },
    )

    settings = ApplicationSettings.create_from_envs()
    assert settings.WEBSERVER_RABBITMQ

    return new_envs


@pytest.fixture
async def second_project(
    client: TestClient,
    logged_user: UserInfoDict,
    tests_data_dir: Path,
    osparc_product_name: ProductName,
    fake_project: ProjectDict,
) -> ProjectDict:
    assert client.app
    async with NewProject(
        {**fake_project, "uuid": None},
        client.app,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        tests_data_dir=tests_data_dir,
    ) as project:
        yield project


async def test_rpc_batch_get_project_custom_metadata_empty_list(
    webserver_rpc_client: WebServerRpcClient,
    product_name: ProductName,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
):
    result = await webserver_rpc_client.projects.batch_get_project_custom_metadata(
        product_name=product_name,
        user_id=logged_user["id"],
        project_uuids=[],
    )
    assert result == {}


async def test_rpc_batch_get_project_custom_metadata_single_project(
    webserver_rpc_client: WebServerRpcClient,
    product_name: ProductName,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    client: TestClient,
):
    assert client.app
    user_id = logged_user["id"]
    project_uuid = ProjectID(user_project["uuid"])

    custom = {"key": "value", "number": 42}
    await set_project_custom_metadata(client.app, user_id, project_uuid, custom)

    result = await webserver_rpc_client.projects.batch_get_project_custom_metadata(
        product_name=product_name,
        user_id=user_id,
        project_uuids=[project_uuid],
    )
    assert result == {project_uuid: custom}


async def test_rpc_batch_get_project_custom_metadata_multiple_projects(
    webserver_rpc_client: WebServerRpcClient,
    product_name: ProductName,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    second_project: ProjectDict,
    client: TestClient,
):
    assert client.app
    user_id = logged_user["id"]
    project_uuid_1 = ProjectID(user_project["uuid"])
    project_uuid_2 = ProjectID(second_project["uuid"])

    custom_1 = {"label": "first", "x": 1}
    custom_2 = {"label": "second", "x": 2}
    await set_project_custom_metadata(client.app, user_id, project_uuid_1, custom_1)
    await set_project_custom_metadata(client.app, user_id, project_uuid_2, custom_2)

    result = await webserver_rpc_client.projects.batch_get_project_custom_metadata(
        product_name=product_name,
        user_id=user_id,
        project_uuids=[project_uuid_1, project_uuid_2],
    )
    assert result == {project_uuid_1: custom_1, project_uuid_2: custom_2}


async def test_rpc_batch_get_project_custom_metadata_not_owned_project(
    webserver_rpc_client: WebServerRpcClient,
    product_name: ProductName,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    client: TestClient,
):
    assert client.app
    project_uuid = ProjectID(user_project["uuid"])

    async with NewUser(
        user_data={
            "name": "other-user",
            "email": "other-user" + logged_user["email"],
        },
        app=client.app,
    ) as other_user:
        with pytest.raises(ProjectForbiddenRpcError):
            await webserver_rpc_client.projects.batch_get_project_custom_metadata(
                product_name=product_name,
                user_id=other_user["id"],
                project_uuids=[project_uuid],
            )


async def test_rpc_batch_get_project_custom_metadata_nonexistent_project(
    webserver_rpc_client: WebServerRpcClient,
    product_name: ProductName,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    faker: Faker,
):
    nonexistent_uuid = ProjectID(faker.uuid4())

    with pytest.raises(ProjectNotFoundRpcError):
        await webserver_rpc_client.projects.batch_get_project_custom_metadata(
            product_name=product_name,
            user_id=logged_user["id"],
            project_uuids=[nonexistent_uuid],
        )
