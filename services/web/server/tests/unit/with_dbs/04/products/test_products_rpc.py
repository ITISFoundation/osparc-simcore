# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Awaitable, Callable
from decimal import Decimal

import pytest
from models_library.api_schemas_webserver import DEFAULT_WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.products import CreditResultRpcGet
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.rabbitmq import RabbitMQRPCClient, RPCServerError
from settings_library.rabbit import RabbitSettings
from simcore_postgres_database.models.users import UserRole
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
async def rpc_client(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    mocker: MockerFixture,
    all_product_prices,
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("client")


async def test_get_credit_amount(
    rpc_client: RabbitMQRPCClient,
    osparc_product_name: ProductName,
    logged_user: UserInfoDict,
):
    # FIXME: use client instead here!
    result = await rpc_client.request(
        DEFAULT_WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_credit_amount"),
        dollar_amount=Decimal(900),
        product_name="s4l",
    )
    credit_result = CreditResultRpcGet.model_validate(result)
    assert credit_result.credit_amount == 100

    result = await rpc_client.request(
        DEFAULT_WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_credit_amount"),
        dollar_amount=Decimal(900),
        product_name="tis",
    )
    credit_result = CreditResultRpcGet.model_validate(result)
    assert credit_result.credit_amount == 180

    with pytest.raises(RPCServerError) as exc_info:
        await rpc_client.request(
            DEFAULT_WEBSERVER_RPC_NAMESPACE,
            TypeAdapter(RPCMethodName).validate_python("get_credit_amount"),
            dollar_amount=Decimal(900),
            product_name="osparc",
        )
    exc = exc_info.value
    assert exc.method_name == "get_credit_amount"
    assert exc.exc_message
    assert exc.traceback
