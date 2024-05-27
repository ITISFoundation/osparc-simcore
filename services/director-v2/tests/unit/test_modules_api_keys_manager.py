# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.auth import ApiKeyCreate, ApiKeyGet
from models_library.products import ProductName
from models_library.projects_nodes_io import NodeID
from models_library.services import RunID
from models_library.users import UserID
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQRPCClient, RPCRouter
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings
from simcore_service_director_v2.modules.osparc_variables._api_auth import (
    get_or_create_user_api_key,
    get_or_create_user_api_secret,
)
from simcore_service_director_v2.modules.osparc_variables.api_keys_manager import (
    _APIKeysManager,
    _get_identifier,
    get_or_create_api_key,
    safe_remove_api_key_and_secret,
)

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def run_id(faker: Faker) -> RunID:
    return RunID(faker.pystr())


@pytest.fixture
def product_name(faker: Faker) -> ProductName:
    return faker.pystr()


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return faker.pyint()


def test_get_api_key_name_is_not_randomly_generated(node_id: NodeID, run_id: RunID):
    api_key_names = {_get_identifier(node_id, run_id) for _ in range(1000)}
    assert len(api_key_names) == 1


@pytest.fixture
def redis_client_sdk(redis_service: RedisSettings) -> RedisClientSDK:
    return RedisClientSDK(
        redis_service.build_redis_dsn(RedisDatabase.DISTRIBUTED_IDENTIFIERS)
    )


@pytest.fixture
async def mock_rpc_server(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    mocker: MockerFixture,
    faker: Faker,
) -> RabbitMQRPCClient:
    rpc_client = await rabbitmq_rpc_client("client")
    rpc_server = await rabbitmq_rpc_client("mock_server")

    router = RPCRouter()

    # mocks the interface defined in the webserver

    _storage: dict[str, ApiKeyGet] = {}

    @router.expose()
    async def api_key_get(
        product_name: ProductName, user_id: UserID, name: str
    ) -> ApiKeyGet | None:
        return _storage.get(f"{product_name}{user_id}", None)

    @router.expose()
    async def create_api_keys(
        product_name: ProductName, user_id: UserID, new: ApiKeyCreate
    ) -> ApiKeyGet:
        api_key = ApiKeyGet(
            display_name=new.display_name,
            api_key=faker.pystr(),
            api_secret=faker.pystr(),
        )
        _storage[f"{product_name}{user_id}"] = api_key
        return api_key

    @router.expose()
    async def delete_api_keys(
        product_name: ProductName, user_id: UserID, name: str
    ) -> None:
        ...

    await rpc_server.register_router(router, namespace=WEBSERVER_RPC_NAMESPACE)

    # mock returned client
    for module_name in ("api_keys_manager", "_api_auth_rpc"):
        mocker.patch(
            f"simcore_service_director_v2.modules.osparc_variables.{module_name}.get_rabbitmq_rpc_client",
            return_value=rpc_client,
            autospec=True,
        )

    return rpc_client


@pytest.fixture
def app() -> FastAPI:
    return FastAPI()


@pytest.fixture
def mock_dynamic_sidecars_scheduler(app: FastAPI, is_service_running: bool) -> None:
    scheduler_mock = AsyncMock()
    scheduler_mock.is_service_tracked = lambda _: is_service_running
    app.state.dynamic_sidecar_scheduler = scheduler_mock


@pytest.fixture
def api_keys_manager(
    mock_rpc_server: RabbitMQRPCClient,
    mock_dynamic_sidecars_scheduler: None,
    redis_client_sdk: RedisClientSDK,
    app: FastAPI,
) -> _APIKeysManager:
    manager = _APIKeysManager(app, redis_client_sdk)
    manager.set_to_app_state(app)
    return manager


async def _get_resource_count(api_keys_manager: _APIKeysManager) -> int:
    return len(await api_keys_manager._get_tracked())  # noqa: SLF001


@pytest.mark.parametrize("is_service_running", [True])
async def test_api_keys_workflow(
    api_keys_manager: _APIKeysManager,
    app: FastAPI,
    node_id: NodeID,
    run_id: RunID,
    product_name: ProductName,
    user_id: UserID,
):
    api_key = await get_or_create_api_key(
        app, product_name=product_name, user_id=user_id, node_id=node_id, run_id=run_id
    )
    assert isinstance(api_key, str)
    assert await _get_resource_count(api_keys_manager) == 1

    await safe_remove_api_key_and_secret(app, node_id=node_id, run_id=run_id)
    assert await _get_resource_count(api_keys_manager) == 0


async def test_user_api_keys(
    app: FastAPI,
    mock_rpc_server: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
):
    user_api_key = await get_or_create_user_api_key(
        app, product_name=product_name, user_id=user_id
    )
    user_api_secret = await get_or_create_user_api_secret(
        app, product_name=product_name, user_id=user_id
    )

    # idempotent
    for _ in range(3):
        assert user_api_key == await get_or_create_user_api_key(
            app, product_name=product_name, user_id=user_id
        )
        assert user_api_secret == await get_or_create_user_api_secret(
            app, product_name=product_name, user_id=user_id
        )


@pytest.mark.parametrize("is_service_running", [False, True])
async def test_background_cleanup(
    api_keys_manager: _APIKeysManager,
    app: FastAPI,
    node_id: NodeID,
    run_id: RunID,
    product_name: ProductName,
    user_id: UserID,
    is_service_running: bool,
) -> None:
    api_key = await get_or_create_api_key(
        app, product_name=product_name, user_id=user_id, node_id=node_id, run_id=run_id
    )
    assert isinstance(api_key, str)
    assert await _get_resource_count(api_keys_manager) == 1

    await api_keys_manager._cleanup_unused_identifiers()  # noqa: SLF001
    assert await _get_resource_count(api_keys_manager) == (
        1 if is_service_running else 0
    )
