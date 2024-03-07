# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Awaitable, Callable, Iterator
from decimal import Decimal
from typing import cast

import pytest
import sqlalchemy as sa
from faker import Faker
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.payments import InvoiceDataGet
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from pytest_simcore.helpers.utils_login import UserInfoDict
from servicelib.rabbitmq import RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings
from simcore_postgres_database.models.users import UserRole
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
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


@pytest.fixture()
def setup_user_pre_registration_details_db(
    postgres_db: sa.engine.Engine, logged_user: UserInfoDict, faker: Faker
) -> Iterator[int]:
    with postgres_db.connect() as con:
        result = con.execute(
            users_pre_registration_details.insert()
            .values(
                user_id=logged_user["id"],
                pre_email=faker.email(),
                pre_first_name=faker.first_name(),
                pre_last_name=faker.last_name(),
                pre_phone=faker.phone_number(),
                company_name=faker.company(),
                address=faker.address().replace("\n", ", "),
                city=faker.city(),
                state=faker.state(),
                country=faker.country(),
                postal_code=faker.postcode(),
                created_by=None,
            )
            .returning(sa.literal_column("*"))
        )
        row = result.fetchone()
        yield cast(int, row[0])
        con.execute(users_pre_registration_details.delete())


@pytest.fixture
async def rpc_server(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    mocker: MockerFixture,
) -> RabbitMQRPCClient:
    rpc_server = await rabbitmq_rpc_client("mock_server")

    from simcore_service_webserver.payments._rpc_invoice import router

    await rpc_server.register_router(router, namespace=WEBSERVER_RPC_NAMESPACE)

    return rpc_server


async def test_get_invoice_data(
    # client: TestClient,
    rpc_server: RabbitMQRPCClient,
    rpc_client: RabbitMQRPCClient,
    osparc_product_name: ProductName,
    logged_user: UserInfoDict,
    setup_user_pre_registration_details_db: None,
):
    result = await rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "get_invoice_data"),
        user_id=logged_user["id"],
        dollar_amount=Decimal(900),
        product_name="s4l",
    )
    invoice_data_get = parse_obj_as(InvoiceDataGet, result)
    assert invoice_data_get
    assert len(invoice_data_get.user_invoice_address.country) == 2
