import json
from pathlib import Path
from unittest import mock

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from pytest_mock import MockerFixture
from simcore_postgres_database.models.resource_tracker import resource_tracker_container
from simcore_service_resource_usage_tracker.modules.prometheus_containers.core import (
    collect_container_resource_usage_task,
)

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def mocked_prometheus_client_custom_query(
    mocker: MockerFixture, project_slug_dir: Path
) -> mock.MagicMock:
    with open(
        project_slug_dir
        / "tests"
        / "unit"
        / "with_dbs"
        / "data"
        / "list_of_prometheus_mocked_outputs.json"
    ) as file:
        data = json.load(file)

    mocked_get_prometheus_api_client = mocker.patch(
        "simcore_service_resource_usage_tracker.modules.prometheus_containers.core._prometheus_sync_client_custom_query",
        autospec=True,
        return_value=data,
    )
    return mocked_get_prometheus_api_client


async def test_collect_container_resource_usage_task(
    mocked_redis_server: None,
    mocked_prometheus: mock.Mock,
    mocked_setup_rabbitmq: mock.MagicMock,
    mocked_prometheus_client_custom_query: mock.MagicMock,
    initialized_app: FastAPI,
    postgres_db: sa.engine.Engine,
):
    await collect_container_resource_usage_task(initialized_app)

    expected_query = "sum without (cpu) (container_cpu_usage_seconds_total{image=~'registry.osparc-master.speag.com/simcore/services/dynamic/jupyter-smash:.*'})[30m:1m]"
    mocked_prometheus_client_custom_query.assert_called_once_with(
        mocked_prometheus.return_value, expected_query, mock.ANY
    )

    db_rows = []
    with postgres_db.connect() as con:
        result = con.execute(sa.select(resource_tracker_container))
        for row in result:
            db_rows.append(row)
    assert len(db_rows) == 10
