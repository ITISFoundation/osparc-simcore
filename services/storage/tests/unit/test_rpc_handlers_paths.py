# pylint:disable=no-name-in-module
# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=too-many-positional-arguments
# pylint:disable=unused-argument
# pylint:disable=unused-variable


from collections.abc import Awaitable, Callable
from pathlib import Path
from unittest import mock

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.projects_nodes_io import LocationID
from models_library.users import UserID
from pytest_mock import MockerFixture
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.storage.paths import compute_path_size
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture
async def storage_rabbitmq_rpc_client(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    rpc_client = await rabbitmq_rpc_client("pytest_storage_rpc_client")
    assert rpc_client
    return rpc_client


@pytest.fixture
async def mock_celery_send_task(mocker: MockerFixture, faker: Faker) -> mock.AsyncMock:
    def mocked_send_task(*args, **kwargs):
        return faker.uuid4()

    return mocker.patch(
        "simcore_service_storage.modules.celery.client.CeleryTaskQueueClient.send_task",
        side_effect=mocked_send_task,
    )


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
async def test_path_compute_size_calls_in_celery(
    initialized_app: FastAPI,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    location_id: LocationID,
    user_id: UserID,
    faker: Faker,
    mock_celery_send_task: mock.AsyncMock,
):
    received, job_id_data = await compute_path_size(
        storage_rabbitmq_rpc_client,
        user_id=user_id,
        product_name=faker.name(),
        location_id=location_id,
        path=Path(faker.file_path(absolute=False)),
    )
    mock_celery_send_task.assert_called_once()
    assert received
    assert job_id_data
