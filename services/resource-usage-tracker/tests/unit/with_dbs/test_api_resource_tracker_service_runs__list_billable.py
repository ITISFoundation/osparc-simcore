from collections.abc import Iterator
from unittest import mock

import httpx
import pytest
import sqlalchemy as sa
from models_library.resource_tracker import CreditTransactionStatus
from simcore_postgres_database.models.resource_tracker_credit_transactions import (
    resource_tracker_credit_transactions,
)
from simcore_postgres_database.models.resource_tracker_service_runs import (
    resource_tracker_service_runs,
)
from starlette import status
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]

_USER_ID = 1
_SERVICE_RUN_ID = "12345"


@pytest.fixture()
def resource_tracker_setup_db(
    postgres_db: sa.engine.Engine,
    random_resource_tracker_service_run,
    random_resource_tracker_credit_transactions,
) -> Iterator[None]:
    with postgres_db.connect() as con:
        con.execute(resource_tracker_service_runs.delete())
        con.execute(resource_tracker_credit_transactions.delete())
        result = con.execute(
            resource_tracker_service_runs.insert()
            .values(
                **random_resource_tracker_service_run(
                    user_id=_USER_ID,
                    service_run_id=_SERVICE_RUN_ID,
                    product_name="osparc",
                )
            )
            .returning(resource_tracker_service_runs)
        )
        row = result.first()
        assert row

        result = con.execute(
            resource_tracker_credit_transactions.insert()
            .values(
                **random_resource_tracker_credit_transactions(
                    user_id=_USER_ID,
                    service_run_id=_SERVICE_RUN_ID,
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


async def test_list_service_runs_which_was_billed(
    mocked_redis_server: None,
    mocked_setup_rabbitmq: mock.Mock,
    postgres_db: sa.engine.Engine,
    resource_tracker_setup_db: dict,
    async_client: httpx.AsyncClient,
):
    url = URL("/v1/services/-/usages")

    response = await async_client.get(
        f'{url.with_query({"product_name": "osparc", "user_id": _USER_ID})}'
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["items"]) == 1
    assert data["total"] == 1

    assert data["items"][0]["credit_cost"] < 0
    assert data["items"][0]["transaction_status"] in list(CreditTransactionStatus)
