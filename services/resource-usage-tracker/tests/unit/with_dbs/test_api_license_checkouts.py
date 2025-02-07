# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments


from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Generator

import pytest
import sqlalchemy as sa
from models_library.api_schemas_resource_usage_tracker.license_checkouts import (
    LicenseCheckoutGet,
    LicenseCheckoutsPage,
)
from models_library.resource_tracker_license_purchases import LicensePurchasesCreate
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    license_checkouts,
    license_purchases,
)
from simcore_postgres_database.models.resource_tracker_license_checkouts import (
    resource_tracker_license_checkouts,
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

        con.execute(resource_tracker_license_checkouts.delete())
        con.execute(resource_tracker_service_runs.delete())


async def test_rpc_license_checkouts_workflow(
    mocked_redis_server: None,
    resource_tracker_service_run_id: str,
    rpc_client: RabbitMQRPCClient,
):
    # List licensed items checkouts
    output = await license_checkouts.get_license_checkouts_page(
        rpc_client,
        product_name="osparc",
        filter_wallet_id=_WALLET_ID,
    )
    assert output.total == 0
    assert output.items == []

    # Purchase license item
    _create_data = LicensePurchasesCreate(
        product_name="osparc",
        license_id="beb16d18-d57d-44aa-a638-9727fa4a72ef",
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
    created_item = await license_purchases.create_license_purchase(
        rpc_client, data=_create_data
    )

    # Checkout with num of seats
    checkout = await license_checkouts.checkout_license(
        rpc_client,
        license_id=created_item.license_id,
        wallet_id=_WALLET_ID,
        product_name="osparc",
        num_of_seats=3,
        service_run_id=resource_tracker_service_run_id,
        user_id=_USER_ID_1,
        user_email="test@test.com",
    )

    # List licensed items checkouts
    output = await license_checkouts.get_license_checkouts_page(
        rpc_client,
        product_name="osparc",
        filter_wallet_id=_WALLET_ID,
    )
    assert output.total == 1
    assert isinstance(output, LicenseCheckoutsPage)

    # Get licensed items checkouts
    output = await license_checkouts.get_license_checkout(
        rpc_client,
        product_name="osparc",
        license_checkout_id=output.items[0].license_checkout_id,
    )
    assert isinstance(output, LicenseCheckoutGet)

    # Release num of seats
    license_item_checkout = await license_checkouts.release_license(
        rpc_client,
        license_checkout_id=checkout.license_checkout_id,
        product_name="osparc",
    )
    assert license_item_checkout
    assert isinstance(license_item_checkout.stopped_at, datetime)
