from collections.abc import Iterator
from decimal import Decimal
from typing import Callable

import httpx
import pytest
import sqlalchemy as sa
from servicelib.rabbitmq import RabbitMQClient
from simcore_postgres_database.models.resource_tracker_credit_transactions import (
    resource_tracker_credit_transactions,
)
from starlette import status
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture()
def resource_tracker_credit_transactions_db(
    postgres_db: sa.engine.Engine,
) -> Iterator[None]:
    with postgres_db.connect() as con:

        yield

        con.execute(resource_tracker_credit_transactions.delete())


async def test_credit_transactions_workflow(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    async_client: httpx.AsyncClient,
    resource_tracker_credit_transactions_db: None,
):
    url = URL("/v1/credit-transactions")

    response = await async_client.post(
        url=f"{url}",
        json={
            "product_name": "osparc",
            "wallet_id": 1,
            "wallet_name": "string",
            "user_id": 1,
            "user_email": "string",
            "osparc_credits": 1234.54,
            "payment_transaction_id": "string",
            "created_at": "2023-08-31T13:04:23.941Z",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["credit_transaction_id"] == 1

    response = await async_client.post(
        url=f"{url}",
        json={
            "product_name": "osparc",
            "wallet_id": 1,
            "wallet_name": "string",
            "user_id": 1,
            "user_email": "string",
            "osparc_credits": 105.5,
            "payment_transaction_id": "string",
            "created_at": "2023-08-31T13:04:23.941Z",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["credit_transaction_id"] == 2

    response = await async_client.post(
        url=f"{url}",
        json={
            "product_name": "osparc",
            "wallet_id": 2,
            "wallet_name": "string",
            "user_id": 1,
            "user_email": "string",
            "osparc_credits": 10.85,
            "payment_transaction_id": "string",
            "created_at": "2023-08-31T13:04:23.941Z",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["credit_transaction_id"] == 3

    url = URL("/v1/credit-transactions/credits:sum")
    response = await async_client.post(
        f'{url.with_query({"product_name": "osparc", "wallet_id": 1})}'
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["wallet_id"] == 1
    assert data["available_osparc_credits"] == Decimal(1340.04)
