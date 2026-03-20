# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import secrets
from uuid import UUID

import pytest
from common_library.users_enums import UserRole
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServiceKey, ServiceVersion
from pydantic import TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.rabbitmq.rpc_interfaces.webserver.errors import NodeNotFoundRpcError
from servicelib.rabbitmq.rpc_interfaces.webserver.v1 import WebServerRpcClient
from settings_library.rabbit import RabbitSettings
from simcore_service_webserver.application_settings import (
    ApplicationSettings,
)
from simcore_service_webserver.projects.models import ProjectDict

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture(scope="session")
def service_name() -> str:
    # Overrides  service_name fixture needed in docker_compose_service_environment_dict fixture
    return "wb-api-server"


@pytest.fixture
def user_role() -> UserRole:
    # for logged_user
    return UserRole.USER


@pytest.fixture
def missing_node_id() -> NodeID:
    return UUID(int=0)


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


async def test_rpc_client_get_node_service_key_version(
    product_name: ProductName,
    webserver_rpc_client: WebServerRpcClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    missing_node_id: NodeID,
):
    # `logged_user` OWNS the `user_project` but not `other_user`
    project_uuid: ProjectID = UUID(user_project["uuid"])
    node_id = secrets.choice(list(user_project["workbench"].keys()))

    service_key, service_version = await webserver_rpc_client.nodes.get_node_service_key_version(
        project_id=project_uuid, node_id=node_id
    )

    assert TypeAdapter(ServiceKey).validate_python(service_key)
    assert TypeAdapter(ServiceVersion).validate_python(service_version)

    with pytest.raises(NodeNotFoundRpcError):
        await webserver_rpc_client.nodes.get_node_service_key_version(project_id=project_uuid, node_id=missing_node_id)
