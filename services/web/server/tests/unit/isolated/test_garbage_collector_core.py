# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from typing import Final
from unittest import mock

import pytest
from faker import Faker
from pytest_mock import MockerFixture
from simcore_service_webserver.garbage_collector._core_orphans import (
    remove_orphaned_services,
)

MODULE_GC_CORE_ORPHANS: Final[
    str
] = "simcore_service_webserver.garbage_collector._core_orphans"


@pytest.fixture
def mock_registry(faker: Faker) -> mock.AsyncMock:
    registry = mock.AsyncMock()
    registry.get_all_resource_keys = mock.AsyncMock(
        return_value=("test_alive_key", None)
    )
    registry.get_resources = mock.AsyncMock(return_value={"project_id": faker.uuid4()})
    return registry


@pytest.fixture
def mock_app() -> mock.AsyncMock:
    return mock.AsyncMock()


@pytest.fixture
def mock_list_node_ids_in_project(
    mocker: MockerFixture, faker: Faker
) -> mock.AsyncMock:
    return mocker.patch(
        f"{MODULE_GC_CORE_ORPHANS}.list_node_ids_in_project",
        autospec=True,
        return_value=set(),
    )


@pytest.fixture
async def mock_list_dynamic_services(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.patch(
        f"{MODULE_GC_CORE_ORPHANS}.director_v2_api.list_dynamic_services",
        autospec=True,
        return_value=[],
    )


async def test_remove_orphaned_services_with_no_running_services_does_nothing(
    mock_list_node_ids_in_project: mock.AsyncMock,
    mock_list_dynamic_services: mock.AsyncMock,
    mock_registry: mock.AsyncMock,
    mock_app: mock.AsyncMock,
):
    await remove_orphaned_services(mock_registry, mock_app)
    mock_list_dynamic_services.assert_called_once()
    mock_list_node_ids_in_project.assert_not_called()


async def test_removed_orphaned_service_of_invalid_service_does_not_hang_or_block_gc(
    mock_list_node_ids_in_project: mock.AsyncMock,
    mock_list_dynamic_services: mock.AsyncMock,
    mock_registry: mock.AsyncMock,
    mock_app: mock.AsyncMock,
):
    mock_list_dynamic_services.return_value = []
    await remove_orphaned_services(mock_registry, mock_app)


# async def test_regression_project_id_recovered_from_the_wrong_data_structure(
#     faker: Faker, mocker: MockerFixture
# ):
#     # tests that KeyError is not raised

#     mocker.patch(
#         f"{MODULE_GC_CORE_ORPHANS}.is_node_id_present_in_any_project_workbench",
#         autospec=True,
#         return_value=True,
#     )
#     mocker.patch(
#         f"{MODULE_GC_CORE_ORPHANS}.ProjectDBAPI.get_from_app_context",
#         autospec=True,
#         return_value=mock.AsyncMock(),
#     )
#     mocker.patch(
#         f"{MODULE_GC_CORE_ORPHANS}.dynamic_scheduler_api.stop_dynamic_service",
#         autospec=True,
#     )

#     await _remove_single_service_if_orphan(
#         app=mock.AsyncMock(),
#         dynamic_service={
#             "service_host": "host",
#             "service_uuid": faker.uuid4(),
#             "user_id": 1,
#             "project_id": faker.uuid4(),
#         },
#         currently_opened_projects_node_ids={},
#     )


# async def test_remove_single_service_if_orphan_service_is_waiting_manual_intervention(
#     faker: Faker,
#     mocker: MockerFixture,
# ):
#     mocker.patch(
#         f"{MODULE_GC_CORE_ORPHANS}.is_node_id_present_in_any_project_workbench",
#         autospec=True,
#         return_value=True,
#     )
#     mocker.patch(
#         f"{MODULE_GC_CORE_ORPHANS}.ProjectDBAPI.get_from_app_context",
#         autospec=True,
#         return_value=mock.AsyncMock(),
#     )

#     # mock settings
#     mocked_settings = mock.AsyncMock()
#     mocked_settings.base_url = URL("http://director-v2:8000/v2")
#     mocked_settings.DIRECTOR_V2_STOP_SERVICE_TIMEOUT = 10
#     mocker.patch(
#         "simcore_service_webserver.director_v2._core_dynamic_services.get_plugin_settings",
#         autospec=True,
#         return_value=mocked_settings,
#     )

#     mocker.patch(
#         "simcore_service_webserver.director_v2._core_base.get_client_session",
#         autospec=True,
#         return_value=ClientSession(),
#     )

#     mocker.patch(
#         f"{MODULE_GC_CORE_ORPHANS}.dynamic_scheduler_api.stop_dynamic_service",
#         side_effect=ServiceWaitingForManualInterventionError,
#     )

#     await _remove_single_service_if_orphan(
#         app=mock.AsyncMock(),
#         dynamic_service={
#             "service_host": "host",
#             "service_uuid": faker.uuid4(),
#             "user_id": 1,
#             "project_id": faker.uuid4(),
#         },
#         currently_opened_projects_node_ids={},
#     )
