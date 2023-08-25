from datetime import datetime, timezone
from typing import Any, Final, Iterator
from unittest import mock

import faker
import httpx
import pytest
import sqlalchemy as sa
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

FAKE: Final = faker.Faker()


def random_resource_tracker_service_run(**overrides) -> dict[str, Any]:
    """Generates random fake data resource tracker DATABASE table"""
    data = dict(
        product_name="osparc",
        service_run_id=FAKE.uuid4(),
        wallet_id=FAKE.pyint(),
        wallet_name=FAKE.word(),
        pricing_plan_id=FAKE.pyint(),
        pricing_detail_id=FAKE.pyint(),
        simcore_user_agent=FAKE.word(),
        user_id=FAKE.pyint(),
        user_email=FAKE.email(),
        project_id=FAKE.uuid4(),
        project_name=FAKE.word(),
        node_id=FAKE.uuid4(),
        node_name=FAKE.word(),
        service_key="simcore/services/dynamic/jupyter-smash",
        service_version="3.0.7",
        service_type="DYNAMIC_SERVICE",
        service_resources={},
        service_additional_metadata={},
        started_at=datetime.now(tz=timezone.utc),
        stopped_at=None,
        service_run_status="RUNNING",
        modified=datetime.now(tz=timezone.utc),
        last_heartbeat_at=datetime.now(tz=timezone.utc),
    )

    data.update(overrides)
    return data


_TOTAL_GENERATED_RESOURCE_TRACKER_SERVICE_RUNS_ROWS = 30
_USER_ID = 1


@pytest.fixture()
def resource_tracker_service_run_db(postgres_db: sa.engine.Engine) -> Iterator[list]:
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


@pytest.mark.testit
async def test_list_service_run_without_wallet(
    mocked_redis_server: None,
    # mocked_setup_background_task: mock.Mock,
    mocked_setup_rabbitmq: mock.Mock,
    # mocked_setup_prometheus_api_client: mock.Mock,
    postgres_db: sa.engine.Engine,
    resource_tracker_service_run_db: dict,
    async_client: httpx.AsyncClient,
):
    url = URL("/v1/usage/services")

    response = await async_client.get(
        f'{url.with_query({"user_id": _USER_ID, "product_name": "osparc"})}'  # , "wallet_id": "", "access_all_wallet_usage": ""
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["items"]) == 20
    assert data["total"] == 30

    response = await async_client.get(
        f'{url.with_query({"user_id": _USER_ID, "product_name": "osparc", "offset": 5, "limit": 10})}'
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["items"]) == 10
    assert data["total"] == 30
    assert data["offset"] == 5
    assert data["limit"] == 10

    response = await async_client.get(
        f'{url.with_query({"user_id": 12345, "product_name": "non-existing"})}'
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["items"]) == 0
    assert data["total"] == 0
