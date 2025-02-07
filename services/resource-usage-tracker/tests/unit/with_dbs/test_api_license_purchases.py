# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

from datetime import UTC, datetime
from decimal import Decimal

import sqlalchemy as sa
from models_library.api_schemas_resource_usage_tracker.license_purchases import (
    LicensePurchaseGet,
    LicensesPurchasesPage,
)
from models_library.resource_tracker_license_purchases import LicensePurchasesCreate
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import license_purchases

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_rpc_license_purchases_workflow(
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    rpc_client: RabbitMQRPCClient,
):
    result = await license_purchases.get_license_purchases_page(
        rpc_client, product_name="osparc", wallet_id=1
    )
    assert isinstance(result, LicensesPurchasesPage)  # nosec
    assert result.items == []
    assert result.total == 0

    _create_data = LicensePurchasesCreate(
        product_name="osparc",
        license_id="beb16d18-d57d-44aa-a638-9727fa4a72ef",
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

    created_item = await license_purchases.create_license_purchase(
        rpc_client, data=_create_data
    )
    assert isinstance(created_item, LicensePurchaseGet)  # nosec

    result = await license_purchases.get_license_purchase(
        rpc_client,
        product_name="osparc",
        licensed_item_purchase_id=created_item.licensed_item_purchase_id,
    )
    assert isinstance(result, LicensePurchaseGet)  # nosec
    assert result.licensed_item_purchase_id == created_item.licensed_item_purchase_id

    result = await license_purchases.get_license_purchases_page(
        rpc_client, product_name="osparc", wallet_id=_create_data.wallet_id
    )
    assert isinstance(result, LicensesPurchasesPage)  # nosec
    assert len(result.items) == 1
    assert result.total == 1
