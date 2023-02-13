# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from unittest.mock import AsyncMock

import pytest
from faker import Faker
from pytest_mock import MockerFixture
from simcore_service_webserver.garbage_collector_core import remove_orphaned_services


@pytest.fixture
def mock_registry(faker: Faker) -> AsyncMock:
    registry = AsyncMock()
    registry.get_all_resource_keys = AsyncMock(return_value=("test_alive_key", None))
    registry.get_resources = AsyncMock(return_value={"project_id": faker.uuid4()})
    return registry


@pytest.fixture
def mock_app() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_get_workbench_node_ids_from_project_uuid(
    mocker: MockerFixture, faker: Faker
) -> None:
    mocker.patch(
        "simcore_service_webserver.garbage_collector_core.get_workbench_node_ids_from_project_uuid",
        return_value={faker.uuid4(), faker.uuid4(), faker.uuid4()},
    )


@pytest.fixture
def mock_list_dynamic_services(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_webserver.garbage_collector_core.director_v2_api.list_dynamic_services",
        autospec=True,
    )


async def test_regression_remove_orphaned_services_node_ids_unhashable_type_set(
    mock_get_workbench_node_ids_from_project_uuid: None,
    mock_list_dynamic_services: None,
    mock_registry: AsyncMock,
    mock_app: AsyncMock,
):
    await remove_orphaned_services(mock_registry, mock_app)
