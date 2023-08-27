from typing import Iterator
from unittest import mock

import httpx
import pytest
import sqlalchemy as sa
from simcore_postgres_database.models.resource_tracker_service_runs import (
    resource_tracker_service_runs,
)
from starlette import status
from yarl import URL

from .conftest import random_resource_tracker_service_run

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


_TOTAL_GENERATED_RESOURCE_TRACKER_SERVICE_RUNS_ROWS = 10
_USER_ID_1 = 1
_USER_ID_2 = 2
_WALLET_ID = 6


@pytest.fixture()
def resource_tracker_service_run_db(postgres_db: sa.engine.Engine) -> Iterator[list]:
    with postgres_db.connect() as con:
        con.execute(resource_tracker_service_runs.delete())
        created_services = []
        for _ in range(_TOTAL_GENERATED_RESOURCE_TRACKER_SERVICE_RUNS_ROWS):
            result = con.execute(
                resource_tracker_service_runs.insert()
                .values(
                    **random_resource_tracker_service_run(
                        user_id=_USER_ID_1, wallet_id=_WALLET_ID
                    )
                )
                .returning(resource_tracker_service_runs)
            )
            row = result.first()
            assert row
            created_services.append(row)

        for _ in range(_TOTAL_GENERATED_RESOURCE_TRACKER_SERVICE_RUNS_ROWS):
            result = con.execute(
                resource_tracker_service_runs.insert()
                .values(
                    **random_resource_tracker_service_run(
                        user_id=_USER_ID_2, wallet_id=_WALLET_ID
                    )
                )
                .returning(resource_tracker_service_runs)
            )
            row = result.first()
            assert row
            created_services.append(row)

        yield created_services

        con.execute(resource_tracker_service_runs.delete())


@pytest.mark.testit
async def test_list_service_runs_with_wallet(
    mocked_redis_server: None,
    mocked_setup_rabbitmq: mock.Mock,
    postgres_db: sa.engine.Engine,
    resource_tracker_service_run_db: dict,
    async_client: httpx.AsyncClient,
):
    url = URL("/v1/usage/services")

    response = await async_client.get(
        f'{url.with_query({"user_id": _USER_ID_1, "product_name": "osparc", "wallet_id": _WALLET_ID, "access_all_wallet_usage": "false"})}'
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["items"]) == 10
    assert data["total"] == 10

    response = await async_client.get(
        f'{url.with_query({"user_id": _USER_ID_1, "product_name": "osparc", "wallet_id": _WALLET_ID, "access_all_wallet_usage": "true"})}'
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["items"]) == 20
    assert data["total"] == 20
