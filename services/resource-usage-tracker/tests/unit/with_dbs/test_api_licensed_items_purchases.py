# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

from datetime import UTC, datetime
from decimal import Decimal

import sqlalchemy as sa
from models_library.api_schemas_resource_usage_tracker.licensed_items_purchases import (
    LicensedItemPurchaseGet,
    LicensedItemsPurchasesPage,
)
from models_library.resource_tracker_licensed_items_purchases import (
    LicensedItemsPurchasesCreate,
)
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    licensed_items_purchases,
)

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_rpc_licensed_items_purchases_workflow(
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    rpc_client: RabbitMQRPCClient,
):
    result = await licensed_items_purchases.get_licensed_items_purchases_page(
        rpc_client, product_name="osparc", wallet_id=1
    )
    assert isinstance(result, LicensedItemsPurchasesPage)  # nosec
    assert result.items == []
    assert result.total == 0

    _create_data = LicensedItemsPurchasesCreate(
        product_name="osparc",
        licensed_item_id="beb16d18-d57d-44aa-a638-9727fa4a72ef",
        key="Duke",
        version="1.0.0",
        wallet_id=1,
        wallet_name="My Wallet",
        pricing_plan_id=1,
        pricing_unit_id=1,
        pricing_unit_cost_id=1,
        pricing_unit_cost=Decimal(10),
        start_at=datetime.now(tz=UTC),
        expire_at=datetime.now(tz=UTC),
        num_of_seats=1,
        purchased_by_user=1,
        user_email="test@test.com",
        purchased_at=datetime.now(tz=UTC),
    )

    created_item = await licensed_items_purchases.create_licensed_item_purchase(
        rpc_client, data=_create_data
    )
    assert isinstance(created_item, LicensedItemPurchaseGet)  # nosec

    result = await licensed_items_purchases.get_licensed_item_purchase(
        rpc_client,
        product_name="osparc",
        licensed_item_purchase_id=created_item.licensed_item_purchase_id,
    )
    assert isinstance(result, LicensedItemPurchaseGet)  # nosec
    assert result.licensed_item_purchase_id == created_item.licensed_item_purchase_id

    result = await licensed_items_purchases.get_licensed_items_purchases_page(
        rpc_client, product_name="osparc", wallet_id=_create_data.wallet_id
    )
    assert isinstance(result, LicensedItemsPurchasesPage)  # nosec
    assert len(result.items) == 1
    assert result.total == 1
