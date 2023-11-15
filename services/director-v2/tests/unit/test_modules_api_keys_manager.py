# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import Awaitable, Callable

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.auth import ApiKeyCreate, ApiKeyGet
from models_library.products import ProductName
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQRPCClient, RPCRouter
from simcore_service_director_v2.modules.api_keys_manager import (
    APIKeysManager,
    get_api_key_name,
)

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


def test_get_api_key_name_is_not_randomly_generated(node_id: NodeID):
    api_key_names = {get_api_key_name(node_id) for x in range(1000)}
    assert len(api_key_names) == 1


@pytest.fixture
async def mock_rpc_server(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    mocker: MockerFixture,
) -> RabbitMQRPCClient:
    rpc_client = await rabbitmq_rpc_client("client")
    rpc_server = await rabbitmq_rpc_client("mock_server")

    router = RPCRouter()

    # mocks the interface defined in the webserver

    @router.expose()
    async def api_key_get(
        product_name: ProductName, user_id: UserID, name: str
    ) -> ApiKeyGet:
        return ApiKeyGet.parse_obj(ApiKeyGet.Config.schema_extra["examples"][0])

    @router.expose()
    async def create_api_keys(
        product_name: ProductName, user_id: UserID, new: ApiKeyCreate
    ) -> ApiKeyGet:
        return ApiKeyGet.parse_obj(ApiKeyGet.Config.schema_extra["examples"][0])

    @router.expose()
    async def delete_api_keys(
        product_name: ProductName, user_id: UserID, name: str
    ) -> None:
        ...

    await rpc_server.register_router(router, namespace=WEBSERVER_RPC_NAMESPACE)

    # mock returned client
    mocker.patch(
        "simcore_service_director_v2.modules.api_key_resource_manager.get_rabbitmq_rpc_client",
        return_value=rpc_client,
    )

    return rpc_client


async def test_rpc_endpoints(
    mock_rpc_server: RabbitMQRPCClient,
    faker: Faker,
):
    manager = APIKeysManager(FastAPI())

    identifier = faker.pystr()
    product_name = faker.pystr()
    user_id = faker.pyint()

    api_key = await manager.get(
        identifier=identifier, product_name=product_name, user_id=user_id
    )
    assert isinstance(api_key, ApiKeyGet)

    identifier, api_key = await manager.create(
        identifier=identifier, product_name=product_name, user_id=user_id
    )
    assert isinstance(identifier, str)
    assert isinstance(api_key, ApiKeyGet)

    await manager.destroy(
        identifier=identifier, product_name=product_name, user_id=user_id
    )
