# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member

import asyncio
from unittest import mock

import distributed
import pytest
from pytest_mock import MockerFixture

# Selection of core and tool services started in this swarm fixture (integration)
pytest_simcore_core_services_selection = [
    "rabbit",
]

pytest_simcore_ops_services_selection = []


def test_rabbitmq_plugin_initializes(dask_client: distributed.Client): ...


@pytest.fixture
def erroring_rabbitmq_plugin(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_dask_sidecar.rabbitmq_worker_plugin.RabbitMQPlugin",
        autospec=True,
        side_effect=RuntimeError("Pytest: RabbitMQ plugin initialization failed"),
    )


async def test_dask_worker_closes_if_plugin_fails_on_start(
    erroring_rabbitmq_plugin: mock.Mock,
    local_cluster: distributed.LocalCluster,
):
    await asyncio.sleep(10)
