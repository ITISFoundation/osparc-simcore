from datetime import datetime, timezone
from typing import Any, Final, Iterator
from unittest import mock

import faker
import httpx
import pytest
import sqlalchemy as sa
from pytest_mock import MockerFixture
from simcore_postgres_database.models.resource_tracker import resource_tracker_container
from starlette import status
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]

FAKE: Final = faker.Faker()


@pytest.fixture
def mocked_setup_background_task(mocker: MockerFixture):
    mocked_background_task = mocker.patch(
        "simcore_service_resource_usage_tracker.core.application.setup_background_task",
        autospec=True,
    )
    return mocked_background_task


@pytest.fixture
def mocked_setup_prometheus_api_client(mocker: MockerFixture):
    mocked_setup_prometheus_api_client = mocker.patch(
        "simcore_service_resource_usage_tracker.core.application.setup_prometheus_api_client",
        autospec=True,
    )
    return mocked_setup_prometheus_api_client


def random_resource_tracker_container(**overrides) -> dict[str, Any]:
    """Generates random fake data resource tracker DATABASE table"""
    data = dict(
        container_id=FAKE.uuid4(),
        user_id=FAKE.pyint(),
        project_uuid=FAKE.uuid4(),
        product_name="osparc",
        cpu_limit="3.5",
        memory_limit="17179869184",
        service_settings_reservation_additional_info={},
        container_cpu_usage_seconds_total=FAKE.pyint(),
        prometheus_created=datetime.now(tz=timezone.utc),
        prometheus_last_scraped=datetime.now(tz=timezone.utc),
        modified=datetime.now(tz=timezone.utc),
        node_uuid=FAKE.uuid4(),
        node_label=FAKE.word(),
        instance="gpu",
        project_name=FAKE.word(),
        user_email=FAKE.email(),
        service_key="simcore/services/dynamic/jupyter-smash",
        service_version="3.0.7",
        classification="USER_SERVICE",
    )

    data.update(overrides)
    return data


_TOTAL_GENERATED_RESOURCE_TRACKER_CONTAINER_ROWS = 30
_USER_ID = 1


@pytest.fixture()
def resource_tracker_container_db(postgres_db: sa.engine.Engine) -> Iterator[list]:
    with postgres_db.connect() as con:
        # removes all projects before continuing
        con.execute(resource_tracker_container.delete())
        created_projects = []
        for _ in range(_TOTAL_GENERATED_RESOURCE_TRACKER_CONTAINER_ROWS):
            result = con.execute(
                resource_tracker_container.insert()
                .values(**random_resource_tracker_container(user_id=_USER_ID))
                .returning(resource_tracker_container)
            )
            project = result.first()
            assert project
            created_projects.append(project)
        yield created_projects

        con.execute(resource_tracker_container.delete())


async def test_list_containers(
    mocked_redis_server: None,
    # mocked_setup_background_task: mock.Mock,
    mocked_setup_prometheus_api_client: mock.Mock,
    postgres_db: sa.engine.Engine,
    resource_tracker_container_db: dict,
    async_client: httpx.AsyncClient,
):
    url = URL("/v1/usage/containers")

    response = await async_client.get(
        f'{url.with_query({"user_id": _USER_ID, "product_name": "osparc"})}'
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

    # MATUS: ADD ADDITIONAL DOMAIN TEST.
    # - check status: running/finished
    # - check duration
    # - check processors/core_hours
