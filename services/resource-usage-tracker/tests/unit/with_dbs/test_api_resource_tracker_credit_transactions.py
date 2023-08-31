from unittest import mock

import httpx
import sqlalchemy as sa
from starlette import status
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_credit_transactions_workflow(
    mocked_redis_server: None,
    mocked_setup_rabbitmq: mock.Mock,
    postgres_db: sa.engine.Engine,
    async_client: httpx.AsyncClient,
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
            "credits": 1234.54,
            "payment_transaction_id": "string",
            "created_at": "2023-08-31T13:04:23.941Z",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    data["credit_transaction_id"] == 1

    response = await async_client.post(
        url=f"{url}",
        json={
            "product_name": "osparc",
            "wallet_id": 1,
            "wallet_name": "string",
            "user_id": 1,
            "user_email": "string",
            "credits": 105.5,
            "payment_transaction_id": "string",
            "created_at": "2023-08-31T13:04:23.941Z",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    data["credit_transaction_id"] == 2

    response = await async_client.post(
        url=f"{url}",
        json={
            "product_name": "osparc",
            "wallet_id": 2,
            "wallet_name": "string",
            "user_id": 1,
            "user_email": "string",
            "credits": 10.85,
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
    assert data["available_credits"] == 1340.04
