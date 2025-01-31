# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Awaitable, Callable

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_resource_usage_tracker.licensed_items_checkouts import (
    LicensedItemCheckoutGet,
)
from models_library.api_schemas_webserver.licensed_items import LicensedItemRpcGetPage
from models_library.licensed_items import VIP_DETAILS_EXAMPLE, LicensedResourceType
from models_library.products import ProductName
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.webserver.licenses.licensed_items import (
    checkout_licensed_item_for_wallet,
    get_available_licensed_items_for_wallet,
    get_licensed_items,
    release_licensed_item_for_wallet,
)
from settings_library.rabbit import RabbitSettings
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.application_settings import ApplicationSettings
from simcore_service_webserver.licenses import _licensed_items_repository

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
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("client")


@pytest.fixture
def mock_get_wallet_by_user(mocker: MockerFixture) -> tuple:
    return mocker.patch(
        "simcore_service_webserver.licenses._licensed_items_checkouts_service.get_wallet_by_user",
        spec=True,
    )


_LICENSED_ITEM_CHECKOUT_GET = LicensedItemCheckoutGet.model_validate(
    LicensedItemCheckoutGet.model_config["json_schema_extra"]["examples"][0]
)


@pytest.fixture
def mock_checkout_licensed_item(mocker: MockerFixture) -> tuple:
    return mocker.patch(
        "simcore_service_webserver.licenses._licensed_items_checkouts_service.licensed_items_checkouts.checkout_licensed_item",
        spec=True,
        return_value=_LICENSED_ITEM_CHECKOUT_GET,
    )


@pytest.fixture
def mock_get_licensed_item_checkout(mocker: MockerFixture) -> tuple:
    return mocker.patch(
        "simcore_service_webserver.licenses._licensed_items_checkouts_service.licensed_items_checkouts.get_licensed_item_checkout",
        spec=True,
        return_value=_LICENSED_ITEM_CHECKOUT_GET,
    )


@pytest.fixture
def mock_release_licensed_item(mocker: MockerFixture) -> tuple:
    return mocker.patch(
        "simcore_service_webserver.licenses._licensed_items_checkouts_service.licensed_items_checkouts.release_licensed_item",
        spec=True,
        return_value=_LICENSED_ITEM_CHECKOUT_GET,
    )


@pytest.mark.acceptance_test(
    "Implements https://github.com/ITISFoundation/osparc-issues/issues/1800"
)
async def test_license_checkout_workflow(
    client: TestClient,
    rpc_client: RabbitMQRPCClient,
    osparc_product_name: ProductName,
    logged_user: UserInfoDict,
    pricing_plan_id: int,
    mock_get_wallet_by_user: MockerFixture,
    mock_checkout_licensed_item: MockerFixture,
    mock_release_licensed_item: MockerFixture,
    mock_get_licensed_item_checkout: MockerFixture,
):
    assert client.app

    result = await get_licensed_items(
        rpc_client, product_name=osparc_product_name, offset=0, limit=20
    )
    assert len(result.items) == 0
    assert result.total == 0

    license_item_db = await _licensed_items_repository.create(
        client.app,
        product_name=osparc_product_name,
        display_name="Model A display name",
        licensed_resource_name="Model A",
        licensed_resource_type=LicensedResourceType.VIP_MODEL,
        pricing_plan_id=pricing_plan_id,
        licensed_resource_data=VIP_DETAILS_EXAMPLE,
    )

    result = await get_licensed_items(
        rpc_client, product_name=osparc_product_name, offset=0, limit=20
    )
    assert len(result.items) == 1
    assert result.total == 1
    assert isinstance(result, LicensedItemRpcGetPage)

    with pytest.raises(NotImplementedError):
        await get_available_licensed_items_for_wallet(
            rpc_client,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
            wallet_id=1,
        )

    checkout = await checkout_licensed_item_for_wallet(
        rpc_client,
        product_name=osparc_product_name,
        user_id=logged_user["id"],
        wallet_id=1,
        licensed_item_id=license_item_db.licensed_item_id,
        num_of_seats=1,
        service_run_id="run_1",
    )

    await release_licensed_item_for_wallet(
        rpc_client,
        product_name=osparc_product_name,
        user_id=logged_user["id"],
        licensed_item_checkout_id=checkout.licensed_item_checkout_id,
    )
