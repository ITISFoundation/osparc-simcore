# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
from decimal import Decimal
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_resource_usage_tracker import (
    licensed_items_purchases as rut_licensed_items_purchases,
)
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    RutPricingPlanGet,
    RutPricingUnitGet,
)
from models_library.api_schemas_webserver.licensed_items import LicensedItemRestGet
from models_library.api_schemas_webserver.licensed_items_purchases import (
    LicensedItemPurchaseGet,
)
from models_library.api_schemas_webserver.wallets import WalletGetWithAvailableCredits
from models_library.licenses import VIP_DETAILS_EXAMPLE, LicensedResourceType
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.licensed_item_to_resource import (
    licensed_item_to_resource,
)
from simcore_postgres_database.models.licensed_items import licensed_items
from simcore_postgres_database.utils_repos import transaction_context
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.licenses import (
    _licensed_items_repository,
    _licensed_resources_repository,
)
from simcore_service_webserver.projects.models import ProjectDict


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_licensed_items_listing(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: str,
    expected: HTTPStatus,
    pricing_plan_id: int,
):
    assert client.app

    # list
    url = client.app.router["list_licensed_items"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data == []

    licensed_item_db = await _licensed_items_repository.create(
        client.app,
        key="Duke",
        version="1.0.0",
        product_name=osparc_product_name,
        display_name="Model A display name",
        licensed_resource_type=LicensedResourceType.VIP_MODEL,
        pricing_plan_id=pricing_plan_id,
    )
    _licensed_item_id = licensed_item_db.licensed_item_id

    got_licensed_resource_duke = (
        await _licensed_resources_repository.create_if_not_exists(
            client.app,
            display_name="Duke",
            licensed_resource_name="Duke",
            licensed_resource_type=LicensedResourceType.VIP_MODEL,
            licensed_resource_data={
                "category_id": "HumanWholeBody",
                "category_display": "Humans",
                "source": VIP_DETAILS_EXAMPLE,
            },
        )
    )

    # Connect them via licensed_item_to_resorce DB table
    async with transaction_context(get_asyncpg_engine(client.app)) as conn:
        await conn.execute(
            licensed_item_to_resource.insert().values(
                licensed_item_id=_licensed_item_id,
                licensed_resource_id=got_licensed_resource_duke.licensed_resource_id,
                product_name=osparc_product_name,
            )
        )

    # list
    url = client.app.router["list_licensed_items"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert LicensedItemRestGet(**data[0])

    # <-- Testing nested camel case
    source = data[0]["licensedResources"][0]["source"]
    assert all("_" not in key for key in source), f"got {source=}"

    # Testing trimmed
    assert "additionalField" not in source
    assert "additional_field" not in source

    # Testing hidden flag
    async with transaction_context(get_asyncpg_engine(client.app)) as conn:
        await conn.execute(
            licensed_items.update()
            .values(
                is_hidden_on_market=True,
            )
            .where(licensed_items.c.licensed_item_id == _licensed_item_id)
        )

    url = client.app.router["list_licensed_items"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data == []


_LICENSED_ITEM_PURCHASE_GET = (
    rut_licensed_items_purchases.LicensedItemPurchaseGet.model_validate(
        {
            "licensed_item_purchase_id": "beb16d18-d57d-44aa-a638-9727fa4a72ef",
            "product_name": "osparc",
            "licensed_item_id": "303942ef-6d31-4ba8-afbe-dbb1fce2a953",
            "key": "Duke",
            "version": "1.0.0",
            "wallet_id": 1,
            "wallet_name": "My Wallet",
            "pricing_unit_cost_id": 1,
            "pricing_unit_cost": Decimal(10),
            "start_at": "2023-01-11 13:11:47.293595",
            "expire_at": "2023-01-11 13:11:47.293595",
            "num_of_seats": 1,
            "purchased_by_user": 1,
            "user_email": "test@test.com",
            "purchased_at": "2023-01-11 13:11:47.293595",
            "modified": "2023-01-11 13:11:47.293595",
        }
    )
)


@pytest.fixture
def mock_licensed_items_purchase_functions(mocker: MockerFixture) -> tuple:
    mock_wallet_credits = mocker.patch(
        "simcore_service_webserver.licenses._licensed_items_service.get_wallet_with_available_credits_by_user_and_wallet",
        spec=True,
        return_value=WalletGetWithAvailableCredits.model_validate(
            WalletGetWithAvailableCredits.model_json_schema()["examples"][0]
        ),
    )
    mock_get_pricing_plan = mocker.patch(
        "simcore_service_webserver.licenses._licensed_items_service.get_pricing_plan",
        spec=True,
        return_value=RutPricingPlanGet.model_validate(
            RutPricingPlanGet.model_json_schema()["examples"][2]
        ),
    )
    mock_get_pricing_unit = mocker.patch(
        "simcore_service_webserver.licenses._licensed_items_service.get_pricing_plan_unit",
        spec=True,
        return_value=RutPricingUnitGet.model_validate(
            RutPricingUnitGet.model_json_schema()["examples"][2]
        ),
    )
    mock_create_licensed_item_purchase = mocker.patch(
        "simcore_service_webserver.licenses._licensed_items_service.licensed_items_purchases.create_licensed_item_purchase",
        return_value=_LICENSED_ITEM_PURCHASE_GET,
    )

    return (
        mock_wallet_credits,
        mock_get_pricing_plan,
        mock_get_pricing_unit,
        mock_create_licensed_item_purchase,
    )


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_licensed_items_purchase(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: str,
    expected: HTTPStatus,
    pricing_plan_id: int,
    mock_licensed_items_purchase_functions: tuple,
):
    assert client.app

    licensed_item_db = await _licensed_items_repository.create(
        client.app,
        key="Duke",
        version="1.0.0",
        product_name=osparc_product_name,
        display_name="Model A display name",
        licensed_resource_type=LicensedResourceType.VIP_MODEL,
        pricing_plan_id=pricing_plan_id,
    )
    _licensed_item_id = licensed_item_db.licensed_item_id

    got_licensed_resource_duke = (
        await _licensed_resources_repository.create_if_not_exists(
            client.app,
            display_name="Duke",
            licensed_resource_name="Duke",
            licensed_resource_type=LicensedResourceType.VIP_MODEL,
            licensed_resource_data={
                "category_id": "HumanWholeBody",
                "category_display": "Humans",
                "source": VIP_DETAILS_EXAMPLE,
            },
        )
    )

    # Connect them via licensed_item_to_resorce DB table
    async with transaction_context(get_asyncpg_engine(client.app)) as conn:
        await conn.execute(
            licensed_item_to_resource.insert().values(
                licensed_item_id=_licensed_item_id,
                licensed_resource_id=got_licensed_resource_duke.licensed_resource_id,
                product_name=osparc_product_name,
            )
        )

    # purchase
    url = client.app.router["purchase_licensed_item"].url_for(
        licensed_item_id=f"{_licensed_item_id}"
    )
    resp = await client.post(
        f"{url}",
        json={
            "wallet_id": 1,
            "num_of_seats": 5,
            "pricing_plan_id": pricing_plan_id,
            "pricing_unit_id": 1,
        },
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert LicensedItemPurchaseGet(**data)
