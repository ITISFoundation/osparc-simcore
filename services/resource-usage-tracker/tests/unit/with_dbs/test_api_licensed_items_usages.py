# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments


from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Generator

import pytest
import sqlalchemy as sa
from models_library.api_schemas_resource_usage_tracker.licensed_items_usages import (
    LicensedItemsUsagesPage,
    LicensedItemUsageGet,
)
from models_library.resource_tracker_licensed_items_purchases import (
    LicensedItemsPurchasesCreate,
)
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    licensed_items_purchases,
    licensed_items_usages,
)
from simcore_postgres_database.models.resource_tracker_licensed_items_usage import (
    resource_tracker_licensed_items_usage,
)
from simcore_postgres_database.models.resource_tracker_service_runs import (
    resource_tracker_service_runs,
)

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


_USER_ID_1 = 1
_WALLET_ID = 6


@pytest.fixture()
def resource_tracker_service_run_id(
    postgres_db: sa.engine.Engine, random_resource_tracker_service_run
) -> Generator[str, None, None]:
    with postgres_db.connect() as con:
        result = con.execute(
            resource_tracker_service_runs.insert()
            .values(
                **random_resource_tracker_service_run(
                    user_id=_USER_ID_1, wallet_id=_WALLET_ID
                )
            )
            .returning(resource_tracker_service_runs.c.service_run_id)
        )
        row = result.first()
        assert row

        yield row[0]

        con.execute(resource_tracker_licensed_items_usage.delete())
        con.execute(resource_tracker_service_runs.delete())


async def test_rpc_licensed_items_usages_workflow(
    mocked_redis_server: None,
    resource_tracker_service_run_id: str,
    rpc_client: RabbitMQRPCClient,
):
    # List licensed items usages
    output = await licensed_items_usages.get_licensed_items_usages_page(
        rpc_client,
        product_name="osparc",
        filter_wallet_id=_WALLET_ID,
    )
    assert output.total == 0
    assert output.items == []

    # Purchase license item
    _create_data = LicensedItemsPurchasesCreate(
        product_name="osparc",
        licensed_item_id="beb16d18-d57d-44aa-a638-9727fa4a72ef",
        wallet_id=_WALLET_ID,
        wallet_name="My Wallet",
        pricing_plan_id=1,
        pricing_unit_id=1,
        pricing_unit_cost_id=1,
        pricing_unit_cost=Decimal(10),
        start_at=datetime.now(tz=UTC),
        expire_at=datetime.now(tz=UTC) + timedelta(days=1),
        num_of_seats=5,
        purchased_by_user=_USER_ID_1,
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
        wallet_id=_WALLET_ID,
        product_name="osparc",
        num_of_seats=3,
        service_run_id=resource_tracker_service_run_id,
        user_id=_USER_ID_1,
        user_email="test@test.com",
    )

    # List licensed items usages
    output = await licensed_items_usages.get_licensed_items_usages_page(
        rpc_client,
        product_name="osparc",
        filter_wallet_id=_WALLET_ID,
    )
    assert output.total == 1
    assert isinstance(output, LicensedItemsUsagesPage)

    # Get licensed items usages
    output = await licensed_items_usages.get_licensed_item_usage(
        rpc_client,
        product_name="osparc",
        licensed_item_usage_id=output.items[0].licensed_item_usage_id,
    )
    assert isinstance(output, LicensedItemUsageGet)

    # Release num of seats
    license_item_usage = await licensed_items_usages.release_licensed_item(
        rpc_client, checkout_id=checkout.checkout_id, product_name="osparc"
    )
    assert license_item_usage
    assert isinstance(license_item_usage.stopped_at, datetime)
