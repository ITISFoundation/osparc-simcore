from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from models_library.api_schemas_resource_usage_tracker.service_runs import (
    ServiceRunPage,
)
from models_library.resource_tracker import (
    CreditTransactionStatus,
    ServiceResourceUsagesFilters,
    StartedAt,
)
from models_library.rest_ordering import OrderBy, OrderDirection
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq._errors import RPCServerError
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import service_runs
from simcore_postgres_database.models.resource_tracker_credit_transactions import (
    resource_tracker_credit_transactions,
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

_USER_ID = 1
_SERVICE_RUN_ID_1 = "12345"
_SERVICE_RUN_ID_2 = "54321"


@pytest.fixture()
def resource_tracker_setup_db(
    postgres_db: sa.engine.Engine,
    random_resource_tracker_service_run,
    random_resource_tracker_credit_transactions,
) -> Iterator[None]:
    with postgres_db.connect() as con:
        con.execute(resource_tracker_service_runs.delete())
        con.execute(resource_tracker_credit_transactions.delete())
        # Service run table
        result = con.execute(
            resource_tracker_service_runs.insert()
            .values(
                **random_resource_tracker_service_run(
                    user_id=_USER_ID,
                    service_run_id=_SERVICE_RUN_ID_1,
                    product_name="osparc",
                    started_at=datetime.now(tz=timezone.utc),
                )
            )
            .returning(resource_tracker_service_runs)
        )
        row = result.first()
        assert row
        result = con.execute(
            resource_tracker_service_runs.insert()
            .values(
                **random_resource_tracker_service_run(
                    user_id=_USER_ID,
                    service_run_id=_SERVICE_RUN_ID_2,
                    product_name="osparc",
                    started_at=datetime.now(tz=timezone.utc) - timedelta(days=1),
                )
            )
            .returning(resource_tracker_service_runs)
        )
        row = result.first()
        assert row

        # Transaction table
        result = con.execute(
            resource_tracker_credit_transactions.insert()
            .values(
                **random_resource_tracker_credit_transactions(
                    user_id=_USER_ID,
                    service_run_id=_SERVICE_RUN_ID_1,
                    product_name="osparc",
                )
            )
            .returning(resource_tracker_credit_transactions)
        )
        row = result.first()
        assert row

        yield

        con.execute(resource_tracker_credit_transactions.delete())
        con.execute(resource_tracker_service_runs.delete())


@pytest.mark.rpc_test()
async def test_rpc_list_service_runs_which_was_billed(
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    resource_tracker_setup_db: dict,
    rpc_client: RabbitMQRPCClient,
):
    result = await service_runs.get_service_run_page(
        rpc_client,
        user_id=_USER_ID,
        product_name="osparc",
    )
    assert isinstance(result, ServiceRunPage)

    assert len(result.items) == 2
    assert result.total == 2
    assert result.items[0].credit_cost < 0
    assert result.items[0].transaction_status in list(CreditTransactionStatus)


@pytest.mark.rpc_test()
async def test_rpc_list_service_runs_with_filtered_by__started_at(
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    resource_tracker_setup_db: dict,
    rpc_client: RabbitMQRPCClient,
):
    result = await service_runs.get_service_run_page(
        rpc_client,
        user_id=_USER_ID,
        product_name="osparc",
        filters=ServiceResourceUsagesFilters(
            started_at=StartedAt(
                from_=datetime.now(timezone.utc) + timedelta(days=1),
                until=datetime.now(timezone.utc) + timedelta(days=1),
            )
        ),
    )
    assert isinstance(result, ServiceRunPage)
    assert len(result.items) == 0
    assert result.total == 0

    result = await service_runs.get_service_run_page(
        rpc_client,
        user_id=_USER_ID,
        product_name="osparc",
        filters=ServiceResourceUsagesFilters(
            started_at=StartedAt(
                from_=datetime.now(timezone.utc),
                until=datetime.now(timezone.utc),
            )
        ),
    )
    assert isinstance(result, ServiceRunPage)
    assert len(result.items) == 1
    assert result.total == 1


@pytest.mark.parametrize(
    "direction,service_run_id",
    [(OrderDirection.DESC, _SERVICE_RUN_ID_1), (OrderDirection.ASC, _SERVICE_RUN_ID_2)],
)
@pytest.mark.rpc_test()
async def test_rpc_list_service_runs_with_order_by__started_at(
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    resource_tracker_setup_db: dict,
    rpc_client: RabbitMQRPCClient,
    direction: OrderDirection,
    service_run_id: str,
):
    result = await service_runs.get_service_run_page(
        rpc_client,
        user_id=_USER_ID,
        product_name="osparc",
        order_by=OrderBy(field="started_at", direction=direction),
    )
    assert isinstance(result, ServiceRunPage)
    assert len(result.items) == 2
    assert result.total == 2

    assert result.items[0].service_run_id == service_run_id


@pytest.mark.rpc_test()
async def test_rpc_list_service_runs_raising_custom_error(
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    resource_tracker_setup_db: dict,
    rpc_client: RabbitMQRPCClient,
):
    with pytest.raises(RPCServerError) as e:
        await service_runs.get_service_run_page(
            rpc_client,
            user_id=_USER_ID,
            product_name="osparc",
            access_all_wallet_usage=True,
        )
    assert e
