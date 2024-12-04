# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterable, Awaitable, Callable

import pytest
import simcore_service_webserver.api_keys._db as db
from aiohttp.test_utils import TestServer
from faker import Faker
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.auth import ApiKeyCreate
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.rabbitmq import RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.api_keys._models import ApiKey
from simcore_service_webserver.api_keys.errors import ApiKeyNotFoundError
from simcore_service_webserver.application_settings import ApplicationSettings

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def app_environment(
    rabbit_service: RabbitSettings,
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
):
    new_envs = setenvs_from_dict(
        monkeypatch,
        {
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
def user_role() -> UserRole:
    return UserRole.USER


@pytest.fixture
async def fake_user_api_keys(
    user_role: UserRole,
    web_server: TestServer,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    faker: Faker,
) -> AsyncIterable[list[ApiKey]]:
    assert web_server.app

    api_keys: list[ApiKey] = [
        await db.create(
            web_server.app,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
            display_name=faker.pystr(),
            expiration=None,
            api_key=faker.pystr(),
            api_secret=faker.pystr(),
        )
        for _ in range(5)
    ]

    yield api_keys

    for api_key in api_keys:
        await db.delete(
            web_server.app,
            api_key_id=api_key.id,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )


@pytest.fixture
async def rpc_client(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    mocker: MockerFixture,
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("client")


async def test_get_api_key(
    fake_user_api_keys: list[ApiKey],
    rpc_client: RabbitMQRPCClient,
    osparc_product_name: ProductName,
    logged_user: UserInfoDict,
):
    for api_key in fake_user_api_keys:
        result = await rpc_client.request(
            WEBSERVER_RPC_NAMESPACE,
            TypeAdapter(RPCMethodName).validate_python("get_api_key"),
            product_name=osparc_product_name,
            user_id=logged_user["id"],
            api_key_id=api_key.id,
        )
        assert result.id == api_key.id


async def test_api_keys_workflow(
    web_server: TestServer,
    rpc_client: RabbitMQRPCClient,
    osparc_product_name: ProductName,
    logged_user: UserInfoDict,
    faker: Faker,
):
    key_name = faker.pystr()

    # creating a key
    created_api_key = await rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("create_api_key"),
        product_name=osparc_product_name,
        user_id=logged_user["id"],
        api_key=ApiKeyCreate(display_name=key_name, expiration=None),
    )
    assert created_api_key.display_name == key_name

    # query the key is still present
    queried_api_key = await rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_api_key"),
        product_name=osparc_product_name,
        user_id=logged_user["id"],
        api_key_id=created_api_key.id,
    )
    assert queried_api_key.display_name == key_name

    assert created_api_key.id == queried_api_key.id
    assert created_api_key.display_name == queried_api_key.display_name

    # remove the key
    delete_key_result = await rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("delete_api_key"),
        product_name=osparc_product_name,
        user_id=logged_user["id"],
        api_key_id=created_api_key.id,
    )
    assert delete_key_result is None

    with pytest.raises(ApiKeyNotFoundError):
        # key no longer present
        await rpc_client.request(
            WEBSERVER_RPC_NAMESPACE,
            TypeAdapter(RPCMethodName).validate_python("get_api_key"),
            product_name=osparc_product_name,
            user_id=logged_user["id"],
            api_key_id=created_api_key.id,
        )
