from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from models_library.api_schemas_resource_usage_tracker.service_runs import (
    OsparcCreditsAggregatedUsagesPage,
)
from models_library.resource_tracker import (
    ServicesAggregatedUsagesTimePeriod,
    ServicesAggregatedUsagesType,
)
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import service_runs
from simcore_postgres_database.models.resource_tracker_credit_transactions import (
    resource_tracker_credit_transactions,
)
from simcore_postgres_database.models.resource_tracker_service_runs import (
    resource_tracker_service_runs,
)

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = [
    "adminer",
]


_USER_ID_1 = 1
_USER_ID_2 = 2
_SERVICE_RUN_ID_1 = "1"
_SERVICE_RUN_ID_2 = "2"
_SERVICE_RUN_ID_3 = "3"
_SERVICE_RUN_ID_4 = "4"
_SERVICE_RUN_ID_5 = "5"
_SERVICE_RUN_ID_6 = "6"
_WALLET_ID = 6


@pytest.fixture()
def resource_tracker_setup_db(
    postgres_db: sa.engine.Engine,
    random_resource_tracker_service_run,
    random_resource_tracker_credit_transactions,
) -> Iterator[None]:
    with postgres_db.connect() as con:
        # Service run table
        result = con.execute(
            resource_tracker_service_runs.insert()
            .values(
                [
                    random_resource_tracker_service_run(
                        user_id=_USER_ID_1,
                        service_run_id=_SERVICE_RUN_ID_1,
                        started_at=datetime.now(tz=timezone.utc) - timedelta(hours=1),
                        stopped_at=datetime.now(tz=timezone.utc),
                        service_run_status="SUCCESS",
                        service_key="simcore/services/dynamic/jupyter-smash",
                    ),
                    random_resource_tracker_service_run(
                        user_id=_USER_ID_2,
                        service_run_id=_SERVICE_RUN_ID_2,
                        started_at=datetime.now(tz=timezone.utc) - timedelta(hours=1),
                        stopped_at=datetime.now(tz=timezone.utc),
                        service_run_status="SUCCESS",
                        service_key="simcore/services/dynamic/jupyter-smash",
                    ),
                    random_resource_tracker_service_run(
                        user_id=_USER_ID_1,
                        service_run_id=_SERVICE_RUN_ID_3,
                        started_at=datetime.now(tz=timezone.utc) - timedelta(hours=1),
                        stopped_at=datetime.now(tz=timezone.utc),
                        service_run_status="SUCCESS",
                        service_key="simcore/services/dynamic/jupyter-smash",
                    ),
                    random_resource_tracker_service_run(
                        user_id=_USER_ID_1,
                        service_run_id=_SERVICE_RUN_ID_4,
                        started_at=datetime.now(tz=timezone.utc) - timedelta(hours=1),
                        stopped_at=datetime.now(tz=timezone.utc),
                        service_run_status="SUCCESS",
                        service_key="simcore/services/dynamic/jupyter-smash",
                    ),
                    random_resource_tracker_service_run(
                        user_id=_USER_ID_1,
                        service_run_id=_SERVICE_RUN_ID_5,
                        started_at=datetime.now(tz=timezone.utc) - timedelta(days=3),
                        stopped_at=datetime.now(tz=timezone.utc),
                        service_run_status="SUCCESS",
                        service_key="simcore/services/dynamic/jupyter-smash",
                    ),
                    random_resource_tracker_service_run(
                        user_id=_USER_ID_1,
                        service_run_id=_SERVICE_RUN_ID_6,
                        started_at=datetime.now(tz=timezone.utc) - timedelta(days=10),
                        stopped_at=datetime.now(tz=timezone.utc),
                        service_run_status="SUCCESS",
                        service_key="simcore/services/dynamic/sim4life",
                    ),
                ]
            )
            .returning(resource_tracker_service_runs)
        )
        row = result.first()
        assert row

        # Transaction table
        result = con.execute(
            resource_tracker_credit_transactions.insert()
            .values(
                [
                    random_resource_tracker_credit_transactions(
                        user_id=_USER_ID_1,
                        service_run_id=_SERVICE_RUN_ID_1,
                        product_name="osparc",
                        transaction_status="BILLED",
                        transaction_classification="DEDUCT_SERVICE_RUN",
                        wallet_id=_WALLET_ID,
                    ),
                    random_resource_tracker_credit_transactions(
                        user_id=_USER_ID_2,
                        service_run_id=_SERVICE_RUN_ID_2,
                        product_name="osparc",
                        transaction_status="BILLED",
                        transaction_classification="DEDUCT_SERVICE_RUN",
                        wallet_id=_WALLET_ID,
                    ),
                    random_resource_tracker_credit_transactions(
                        user_id=_USER_ID_1,
                        service_run_id=_SERVICE_RUN_ID_4,
                        product_name="osparc",
                        transaction_status="BILLED",
                        transaction_classification="DEDUCT_SERVICE_RUN",
                        wallet_id=_WALLET_ID,
                    ),
                    random_resource_tracker_credit_transactions(
                        user_id=_USER_ID_1,
                        service_run_id=_SERVICE_RUN_ID_5,
                        product_name="osparc",
                        transaction_status="BILLED",
                        transaction_classification="DEDUCT_SERVICE_RUN",
                        wallet_id=_WALLET_ID,
                    ),
                    random_resource_tracker_credit_transactions(
                        user_id=_USER_ID_1,
                        service_run_id=_SERVICE_RUN_ID_6,
                        product_name="osparc",
                        transaction_status="BILLED",
                        transaction_classification="DEDUCT_SERVICE_RUN",
                        wallet_id=_WALLET_ID,
                    ),
                ]
            )
            .returning(resource_tracker_credit_transactions)
        )
        row = result.first()
        assert row

        yield

        con.execute(resource_tracker_credit_transactions.delete())
        con.execute(resource_tracker_service_runs.delete())


async def test_rpc_get_osparc_credits_aggregated_usages_page(
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    rpc_client: RabbitMQRPCClient,
    resource_tracker_setup_db: dict,
):
    result = await service_runs.get_osparc_credits_aggregated_usages_page(
        rpc_client,
        user_id=_USER_ID_1,
        product_name="osparc",
        aggregated_by=ServicesAggregatedUsagesType.services,
        time_period=ServicesAggregatedUsagesTimePeriod.ONE_DAY,
        wallet_id=123,  # <-- testing non existing wallet
        access_all_wallet_usage=False,
    )
    assert isinstance(result, OsparcCreditsAggregatedUsagesPage)
    assert len(result.items) == 0
    assert result.total == 0

    result = await service_runs.get_osparc_credits_aggregated_usages_page(
        rpc_client,
        user_id=_USER_ID_1,
        product_name="osparc",
        aggregated_by=ServicesAggregatedUsagesType.services,
        time_period=ServicesAggregatedUsagesTimePeriod.ONE_DAY,  # <-- testing
        wallet_id=_WALLET_ID,
        access_all_wallet_usage=False,
    )
    assert isinstance(result, OsparcCreditsAggregatedUsagesPage)
    assert len(result.items) == 1
    assert result.total == 1
    first_osparc_credits = result.items[0].osparc_credits

    result = await service_runs.get_osparc_credits_aggregated_usages_page(
        rpc_client,
        user_id=_USER_ID_1,
        product_name="osparc",
        aggregated_by=ServicesAggregatedUsagesType.services,
        time_period=ServicesAggregatedUsagesTimePeriod.ONE_DAY,
        wallet_id=_WALLET_ID,
        access_all_wallet_usage=True,  # <-- testing
    )
    assert isinstance(result, OsparcCreditsAggregatedUsagesPage)
    assert len(result.items) == 1
    assert result.total == 1
    second_osparc_credits = result.items[0].osparc_credits
    assert second_osparc_credits < first_osparc_credits

    result = await service_runs.get_osparc_credits_aggregated_usages_page(
        rpc_client,
        user_id=_USER_ID_1,
        product_name="osparc",
        aggregated_by=ServicesAggregatedUsagesType.services,
        time_period=ServicesAggregatedUsagesTimePeriod.ONE_WEEK,  # <-- testing
        wallet_id=_WALLET_ID,
        access_all_wallet_usage=False,
    )
    assert isinstance(result, OsparcCreditsAggregatedUsagesPage)
    assert len(result.items) == 1
    assert result.total == 1
    third_osparc_credits = result.items[0].osparc_credits
    assert third_osparc_credits < first_osparc_credits

    result = await service_runs.get_osparc_credits_aggregated_usages_page(
        rpc_client,
        user_id=_USER_ID_1,
        product_name="osparc",
        aggregated_by=ServicesAggregatedUsagesType.services,
        time_period=ServicesAggregatedUsagesTimePeriod.ONE_MONTH,  # <-- testing
        wallet_id=_WALLET_ID,
        access_all_wallet_usage=False,
    )
    assert isinstance(result, OsparcCreditsAggregatedUsagesPage)
    assert len(result.items) == 2
    assert result.total == 2
