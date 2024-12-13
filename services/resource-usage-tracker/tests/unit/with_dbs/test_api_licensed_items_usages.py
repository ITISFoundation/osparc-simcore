# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments


from datetime import UTC, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa
from models_library.resource_tracker_licensed_items_purchases import (
    LicensedItemsPurchasesCreate,
)
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    licensed_items_purchases,
    licensed_items_usages,
)

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_service_licensed_items_usages(
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    rpc_client: RabbitMQRPCClient,
):
    ...

    # List licensed items usages

    # Get licensed items usages


async def test_rpc_licensed_items_usages_workflow(
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    rpc_client: RabbitMQRPCClient,
):
    # Purchase license item
    _create_data = LicensedItemsPurchasesCreate(
        product_name="osparc",
        licensed_item_id="beb16d18-d57d-44aa-a638-9727fa4a72ef",
        wallet_id=1,
        wallet_name="My Wallet",
        pricing_plan_id=1,
        pricing_unit_id=1,
        pricing_unit_cost_id=1,
        pricing_unit_cost=Decimal(10),
        start_at=datetime.now(tz=UTC),
        expire_at=datetime.now(tz=UTC) + timedelta(days=1),
        num_of_seats=5,
        purchased_by_user=1,
        user_email="test@test.com",
        purchased_at=datetime.now(tz=UTC),
    )

    created_item = await licensed_items_purchases.create_licensed_item_purchase(
        rpc_client, data=_create_data
    )

    # Checkout with num of seats
    checkout = await licensed_items_usages.checkout_licensed_item(
        rpc_client,
        licensed_item_id=created_item.licensed_item_id,
        wallet_id=1,
        product_name="osparc",
        num_of_seats=3,
        service_run_id="run_1",
        user_id=1,
        user_email="test@test.com",
    )

    # Release num of seats
    license_item_usage = await licensed_items_usages.release_licensed_item(
        rpc_client, checkout_id=checkout.checkout_id, product_name="osparc"
    )
    assert license_item_usage


# TODO: MD
# Add test for heartbeat check!
