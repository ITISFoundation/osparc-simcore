# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from typing import Callable, Final
from unittest import mock

import pytest
from faker import Faker
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_mock import MockerFixture
from simcore_service_webserver.garbage_collector._core_orphans import (
    remove_orphaned_services,
)
from simcore_service_webserver.resource_manager.registry import UserSessionDict

MODULE_GC_CORE_ORPHANS: Final[
    str
] = "simcore_service_webserver.garbage_collector._core_orphans"


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return faker.pyint(min_value=1)


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def client_session_id(faker: Faker) -> str:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def mock_registry(
    user_id: UserID, project_id: ProjectID, client_session_id: str
) -> mock.AsyncMock:
    async def _fake_get_all_resource_keys() -> tuple[
        list[UserSessionDict], list[UserSessionDict]
    ]:
        return ([{"user_id": user_id, "client_session_id": client_session_id}], [])

    registry = mock.AsyncMock()
    registry.get_all_resource_keys = mock.AsyncMock(
        side_effect=_fake_get_all_resource_keys
    )
    registry.get_resources = mock.AsyncMock(
        return_value={"project_id": f"{project_id}"}
    )
    return registry


@pytest.fixture
def mock_app() -> mock.AsyncMock:
    return mock.AsyncMock()


@pytest.fixture
def mock_list_node_ids_in_project(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.patch(
        f"{MODULE_GC_CORE_ORPHANS}.list_node_ids_in_project",
        autospec=True,
        return_value=set(),
    )


@pytest.fixture(params=[False, True], ids=lambda s: f"node-present-in-project:{s}")
def node_exists(request: pytest.FixtureRequest) -> bool:
    return request.param


@pytest.fixture
async def mock_is_node_id_present_in_any_project_workbench(
    mocker: MockerFixture, node_exists: bool
) -> mock.AsyncMock:
    return mocker.patch(
        f"{MODULE_GC_CORE_ORPHANS}.is_node_id_present_in_any_project_workbench",
        autospec=True,
        return_value=node_exists,
    )


@pytest.fixture
async def mock_list_dynamic_services(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.patch(
        f"{MODULE_GC_CORE_ORPHANS}.director_v2_api.list_dynamic_services",
        autospec=True,
        return_value=[],
    )


@pytest.fixture
async def mock_stop_dynamic_service(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.patch(
        f"{MODULE_GC_CORE_ORPHANS}.dynamic_scheduler_api.stop_dynamic_service",
        autospec=True,
    )


async def test_remove_orphaned_services_with_no_running_services_does_nothing(
    mock_list_node_ids_in_project: mock.AsyncMock,
    mock_list_dynamic_services: mock.AsyncMock,
    mock_is_node_id_present_in_any_project_workbench: mock.AsyncMock,
    mock_stop_dynamic_service: mock.AsyncMock,
    mock_registry: mock.AsyncMock,
    mock_app: mock.AsyncMock,
):
    await remove_orphaned_services(mock_registry, mock_app)
    mock_list_dynamic_services.assert_called_once()
    mock_list_node_ids_in_project.assert_not_called()
    mock_is_node_id_present_in_any_project_workbench.assert_not_called()
    mock_stop_dynamic_service.assert_not_called()


@pytest.fixture
def faker_dynamic_service_get() -> Callable[[], DynamicServiceGet]:
    def _() -> DynamicServiceGet:
        return DynamicServiceGet.parse_obj(
            DynamicServiceGet.Config.schema_extra["examples"][1]
        )

    return _


@pytest.fixture(params=[False, True], ids=lambda s: f"has-write-permission:{s}")
def has_write_permission(request: pytest.FixtureRequest) -> bool:
    return request.param


@pytest.fixture
async def mock_has_write_permission(
    mocker: MockerFixture, has_write_permission: bool
) -> mock.AsyncMock:
    mocked_project_db_api = mocker.patch(
        f"{MODULE_GC_CORE_ORPHANS}.ProjectDBAPI", autospec=True
    )

    async def _mocked_has_permission(*args, **kwargs) -> bool:
        assert "write" in args
        return has_write_permission

    mocked_project_db_api.get_from_app_context.return_value.has_permission.side_effect = (
        _mocked_has_permission
    )
    return mocked_project_db_api.get_from_app_context.return_value.has_permission


async def test_remove_orphaned_services(
    mock_list_node_ids_in_project: mock.AsyncMock,
    mock_is_node_id_present_in_any_project_workbench: mock.AsyncMock,
    mock_list_dynamic_services: mock.AsyncMock,
    mock_stop_dynamic_service: mock.AsyncMock,
    mock_has_write_permission: mock.AsyncMock,
    mock_registry: mock.AsyncMock,
    mock_app: mock.AsyncMock,
    faker_dynamic_service_get: Callable[[], DynamicServiceGet],
    project_id: ProjectID,
    request: pytest.FixtureRequest,
):
    fake_running_service = faker_dynamic_service_get()
    mock_list_dynamic_services.return_value = [fake_running_service]
    await remove_orphaned_services(mock_registry, mock_app)
    mock_list_dynamic_services.assert_called_once()
    mock_is_node_id_present_in_any_project_workbench.assert_called_once_with(
        mock.ANY, fake_running_service.node_uuid
    )
    mock_list_node_ids_in_project.assert_called_once_with(mock.ANY, project_id)

    if is_node_present := request.getfixturevalue(
        "mock_is_node_id_present_in_any_project_workbench"
    ):
        mock_has_write_permission.assert_not_called()
    else:
        mock_has_write_permission.assert_not_called()
    mock_stop_dynamic_service.assert_called_once_with(
        mock_app,
        node_id=fake_running_service.node_uuid,
        simcore_user_agent=mock.ANY,
        save_state=False,
    )


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
