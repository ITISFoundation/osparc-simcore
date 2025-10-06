# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Awaitable, Callable
from decimal import Decimal

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver import DEFAULT_WEBSERVER_RPC_NAMESPACE
from models_library.payments import InvoiceDataGet
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.rabbitmq import RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings
from simcore_service_webserver.application_settings import ApplicationSettings
from simcore_service_webserver.payments.settings import (
    PaymentsSettings,
    get_plugin_settings,
)

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
async def rpc_client(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    latest_osparc_price: Decimal,
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("client")


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


@pytest.mark.acceptance_test(
    "For https://github.com/ITISFoundation/osparc-simcore/issues/4657"
)
async def test_one_time_payment_worfklow(
    client: TestClient,
    logged_user: UserInfoDict,
    setup_user_pre_registration_details_db: None,
    rpc_client: RabbitMQRPCClient,
):
    assert client.app
    settings: PaymentsSettings = get_plugin_settings(client.app)

    assert settings.PAYMENTS_FAKE_COMPLETION is False

    result = await rpc_client.request(
        DEFAULT_WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_invoice_data"),
        user_id=logged_user["id"],
        dollar_amount=Decimal(900),
        product_name="osparc",
    )
    invoice_data_get = InvoiceDataGet.model_validate(result)
    assert invoice_data_get
    assert len(invoice_data_get.user_invoice_address.country) == 2
