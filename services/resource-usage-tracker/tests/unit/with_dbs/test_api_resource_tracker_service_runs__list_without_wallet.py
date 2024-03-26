from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from models_library.api_schemas_resource_usage_tracker.service_runs import (
    ServiceRunPage,
)
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import service_runs
from simcore_postgres_database.models.resource_tracker_service_runs import (
    resource_tracker_service_runs,
)

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = [
    "adminer",
]


_TOTAL_GENERATED_RESOURCE_TRACKER_SERVICE_RUNS_ROWS = 30
_USER_ID = 1


@pytest.fixture()
def resource_tracker_service_run_db(
    postgres_db: sa.engine.Engine, random_resource_tracker_service_run
) -> Iterator[list]:
    with postgres_db.connect() as con:
        # removes all projects before continuing
        con.execute(resource_tracker_service_runs.delete())
        created_services = []
        for _ in range(_TOTAL_GENERATED_RESOURCE_TRACKER_SERVICE_RUNS_ROWS):
            result = con.execute(
                resource_tracker_service_runs.insert()
                .values(**random_resource_tracker_service_run(user_id=_USER_ID))
                .returning(resource_tracker_service_runs)
            )
            row = result.first()
            assert row
            created_services.append(row)
        yield created_services

        con.execute(resource_tracker_service_runs.delete())


@pytest.mark.rpc_test()
async def test_rpc_list_service_runs_with_wallet(
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    resource_tracker_service_run_db: dict,
    rpc_client: RabbitMQRPCClient,
):
    result = await service_runs.get_service_run_page(
        rpc_client,
        user_id=_USER_ID,
        product_name="osparc",
    )
    assert isinstance(result, ServiceRunPage)
    assert len(result.items) == 20
    assert result.total == 30

    result = await service_runs.get_service_run_page(
        rpc_client, user_id=_USER_ID, product_name="osparc", offset=5, limit=10
    )
    assert isinstance(result, ServiceRunPage)
    assert len(result.items) == 10
    assert result.total == 30

    result = await service_runs.get_service_run_page(
        rpc_client,
        user_id=12345,
        product_name="non-existing",
    )
    assert isinstance(result, ServiceRunPage)
    assert len(result.items) == 0
    assert result.total == 0
