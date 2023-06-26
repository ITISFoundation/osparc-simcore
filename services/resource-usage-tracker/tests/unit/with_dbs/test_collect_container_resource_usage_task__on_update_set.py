import logging
import random
from pathlib import Path
from unittest import mock

import arrow
import pytest
import sqlalchemy as sa
from faker import Faker
from fastapi import FastAPI
from pytest_mock import MockerFixture
from simcore_postgres_database.models.resource_tracker import resource_tracker_container
from simcore_service_resource_usage_tracker.resource_tracker_core import (
    collect_container_resource_usage_task,
)

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]

_logger = logging.getLogger(__name__)

_END_DATETIME = 1687132800
_START_DATETIME = 1687046400
_NUM_OF_GENERATED_OUTPUTS = 20


def _update_variable_if_smaller(existing_value, new_value):
    if existing_value is None or new_value < existing_value:
        existing_value = new_value
    return existing_value


def _update_variable_if_bigger(existing_value, new_value):
    if existing_value is None or new_value > existing_value:
        existing_value = new_value
    return existing_value


@pytest.fixture
def random_promql_output_generator():
    random_seed = random.randint(0, 100)
    _logger.info("Random seed %s", random_seed)
    Faker.seed(random_seed)
    faker = Faker()

    generated_data: list = []
    min_timestamp_value: int | None = None
    max_timestamp_value: int | None = None
    max_float_value: float | None = None

    for _ in range(_NUM_OF_GENERATED_OUTPUTS):
        a = faker.unix_time(end_datetime=_END_DATETIME, start_datetime=_START_DATETIME)
        b = faker.unix_time(end_datetime=_END_DATETIME, start_datetime=_START_DATETIME)
        (smaller_timestamp, bigger_timestamp) = (a, b) if a < b else (b, a)

        random_float = faker.pyfloat(
            positive=True, min_value=0.157543565, max_value=500
        )

        min_timestamp_value = _update_variable_if_smaller(
            min_timestamp_value, smaller_timestamp
        )
        max_timestamp_value = _update_variable_if_bigger(
            max_timestamp_value, bigger_timestamp
        )
        max_float_value = _update_variable_if_bigger(max_float_value, random_float)

        data_point = {
            "metric": {
                "container_label_com_docker_compose_oneoff": "False",
                "container_label_com_docker_compose_project_working_dir": "/tmp/tmp_3seh6kp",
                "container_label_com_docker_compose_version": "1.29.1",
                "container_label_product_name": "osparc",
                "container_label_simcore_service_settings": '[{"name": "ports", "type": "int", "value": 8888}, {"name": "env", "type": "string", "value": ["DISPLAY=:0"]}, {"name": "env", "type": "string", "value": ["SYM_SERVER_HOSTNAME=sym-server_%service_uuid%"]}, {"name": "mount", "type": "object", "value": [{"ReadOnly": true, "Source": "/tmp/.X11-unix", "Target": "/tmp/.X11-unix", "Type": "bind"}]}, {"name": "constraints", "type": "string", "value": ["node.platform.os == linux"]}, {"name": "Resources", "type": "Resources", "value": {"Limits": {"NanoCPUs": 4000000000, "MemoryBytes": 17179869184}, "Reservations": {"NanoCPUs": 100000000, "MemoryBytes": 536870912, "GenericResources": [{"DiscreteResourceSpec": {"Kind": "VRAM", "Value": 1}}]}}}]',
                "container_label_simcore_user_agent": "puppeteer",
                "container_label_study_id": "46449cc3-7d83-4081-a44e-fc75a0c85f2c",
                "container_label_user_id": "43820",
                "container_label_uuid": "2b231c38-0ebc-5cc0-1234-1ffe573f54e9",
                "id": "/docker/58e1138d51eb5eafd737024d0df0b01ef88f2087e5a3922565c59130d57ac7a3",
                "image": "registry.osparc.io/simcore/services/dynamic/jupyter-smash:3.0.7",
                "instance": "gpu1",
                "job": "cadvisor",
                "name": "dy-sidecar-2b231c38-0ebc-5cc0-1234-1ffe573f54e9-0-jupyter-smash",
            },
            "values": [
                [smaller_timestamp, "0.157543565"],
                [bigger_timestamp, random_float],
            ],
        }
        generated_data.append(data_point)

    return {
        "data": generated_data,
        "min_timestamp": min_timestamp_value,
        "max_timestamp": max_timestamp_value,
        "max_float": max_float_value,
    }


@pytest.fixture
def mocked_prometheus_client_custom_query(
    mocker: MockerFixture, project_slug_dir: Path, random_promql_output_generator
) -> dict[str, mock.Mock]:
    mocked_get_prometheus_api_client = mocker.patch(
        "simcore_service_resource_usage_tracker.resource_tracker_core._prometheus_sync_client_custom_query",
        autospec=True,
        return_value=random_promql_output_generator["data"],
    )
    return mocked_get_prometheus_api_client


async def test_collect_container_resource_usage_task(
    mocked_prometheus,
    mocked_prometheus_client_custom_query,
    initialized_app: FastAPI,
    postgres_db,
    random_promql_output_generator,
):
    await collect_container_resource_usage_task(initialized_app)

    expected_query = "sum without (cpu) (container_cpu_usage_seconds_total{image=~'registry.osparc-master.speag.com/simcore/services/dynamic/jupyter-smash:.*'})[30m:1m]"
    mocked_prometheus_client_custom_query.assert_called_once_with(
        mocked_prometheus.return_value, expected_query
    )

    db_rows = []
    with postgres_db.connect() as con:
        result = con.execute(sa.select(resource_tracker_container))
        for row in result:
            db_rows.append(row)
    assert len(db_rows) == 1

    assert (
        random_promql_output_generator["max_float"] == db_rows[0][8]
    )  # <-- container_cpu_usage_seconds_total
    assert (
        arrow.get(random_promql_output_generator["min_timestamp"]).datetime
        == db_rows[0][9]
    )  # <-- prometheus_created
    assert (
        arrow.get(random_promql_output_generator["max_timestamp"]).datetime
        == db_rows[0][10]
    )  # <-- prometheus_last_scraped
