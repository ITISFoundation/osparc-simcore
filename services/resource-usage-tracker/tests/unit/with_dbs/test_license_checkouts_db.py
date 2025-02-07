# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments


from datetime import UTC, datetime
from typing import Generator
from unittest import mock

import pytest
import sqlalchemy as sa
from models_library.basic_types import IDStr
from models_library.rest_ordering import OrderBy
from simcore_postgres_database.models.resource_tracker_license_checkouts import (
    resource_tracker_license_checkouts,
)
from simcore_postgres_database.models.resource_tracker_service_runs import (
    resource_tracker_service_runs,
)
from simcore_service_resource_usage_tracker.models.license_checkouts import (
    CreateLicenseCheckoutDB,
)
from simcore_service_resource_usage_tracker.services.modules.db import (
    license_checkouts_db,
)

pytest_simcore_core_services_selection = [
    "postgres",
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


async def test_license_checkouts_db__force_release_license_seats_by_run_id(
    mocked_redis_server: None,
    mocked_setup_rabbitmq: mock.Mock,
    resource_tracker_service_run_id,
    initialized_app,
):
    engine = initialized_app.state.engine

    # SETUP
    _create_license_item_checkout_db_1 = CreateLicenseCheckoutDB(
        license_id="beb16d18-d57d-44aa-a638-9727fa4a72ef",
        wallet_id=_WALLET_ID,
        user_id=_USER_ID_1,
        user_email="test@test.com",
        product_name="osparc",
        service_run_id=resource_tracker_service_run_id,
        started_at=datetime.now(tz=UTC),
        num_of_seats=1,
    )
    await license_checkouts_db.create(engine, data=_create_license_item_checkout_db_1)

    _create_license_item_checkout_db_2 = _create_license_item_checkout_db_1.model_dump()
    _create_license_item_checkout_db_2[
        "license_id"
    ] = "b1b96583-333f-44d6-b1e0-5c0a8af555bf"
    await license_checkouts_db.create(
        engine,
        data=CreateLicenseCheckoutDB.model_construct(
            **_create_license_item_checkout_db_2
        ),
    )

    _create_license_item_checkout_db_3 = _create_license_item_checkout_db_1.model_dump()
    _create_license_item_checkout_db_3[
        "license_id"
    ] = "38a5ce59-876f-482a-ace1-d3b2636feac6"
    checkout = await license_checkouts_db.create(
        engine,
        data=CreateLicenseCheckoutDB.model_construct(
            **_create_license_item_checkout_db_3
        ),
    )

    _helper_time = datetime.now(UTC)
    await license_checkouts_db.update(
        engine,
        license_checkout_id=checkout.license_checkout_id,
        product_name="osparc",
        stopped_at=_helper_time,
    )

    # TEST FORCE RELEASE LICENSE SEATS
    await license_checkouts_db.force_release_license_seats_by_run_id(
        engine, service_run_id=resource_tracker_service_run_id
    )

    # ASSERT
    total, items = await license_checkouts_db.list_(
        engine,
        product_name="osparc",
        filter_wallet_id=_WALLET_ID,
        offset=0,
        limit=5,
        order_by=OrderBy(field=IDStr("started_at")),
    )
    assert total == 3
    assert len(items) == 3

    _helper_count = 0
    for item in items:
        assert isinstance(item.stopped_at, datetime)
        if item.stopped_at > _helper_time:
            _helper_count += 1

    assert _helper_count == 2
