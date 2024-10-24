# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=unused-argument

from collections.abc import Callable
from typing import Final
from unittest import mock

import pytest
from faker import Faker
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStop,
)
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_mock import MockerFixture
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.garbage_collector._core_orphans import (
    remove_orphaned_services,
)
from simcore_service_webserver.resource_manager.registry import UserSessionDict
from simcore_service_webserver.users.exceptions import UserNotFoundError

MODULE_GC_CORE_ORPHANS: Final[
    str
] = "simcore_service_webserver.garbage_collector._core_orphans"


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
    async def _fake_get_all_resource_keys() -> (
        tuple[list[UserSessionDict], list[UserSessionDict]]
    ):
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
        return DynamicServiceGet.model_validate(
            DynamicServiceGet.model_config["json_schema_extra"]["examples"][1]
        )

    return _


@pytest.fixture(params=[False, True], ids=lambda s: f"has-write-permission:{s}")
def has_write_permission(request: pytest.FixtureRequest) -> bool:
    return request.param


@pytest.fixture
async def mock_has_write_permission(
    mocker: MockerFixture, has_write_permission: bool
) -> mock.AsyncMock:
    return mocker.patch(
        f"{MODULE_GC_CORE_ORPHANS}.has_user_project_access_rights",
        autospec=True,
        return_value=has_write_permission,
    )


@pytest.fixture(params=list(UserRole), ids=str)
def user_role(request: pytest.FixtureRequest) -> UserRole:
    return request.param


@pytest.fixture
async def mock_get_user_role(
    mocker: MockerFixture, user_role: UserRole
) -> mock.AsyncMock:
    return mocker.patch(
        f"{MODULE_GC_CORE_ORPHANS}.get_user_role", autospec=True, return_value=user_role
    )


async def test_remove_orphaned_services(
    mock_app: mock.AsyncMock,
    mock_registry: mock.AsyncMock,
    mock_list_node_ids_in_project: mock.AsyncMock,
    mock_is_node_id_present_in_any_project_workbench: mock.AsyncMock,
    mock_list_dynamic_services: mock.AsyncMock,
    mock_stop_dynamic_service: mock.AsyncMock,
    mock_has_write_permission: mock.AsyncMock,
    mock_get_user_role: mock.AsyncMock,
    faker_dynamic_service_get: Callable[[], DynamicServiceGet],
    project_id: ProjectID,
    node_exists: bool,
    has_write_permission: bool,
    user_role: UserRole,
):
    fake_running_service = faker_dynamic_service_get()
    mock_list_dynamic_services.return_value = [fake_running_service]
    await remove_orphaned_services(mock_registry, mock_app)
    mock_list_dynamic_services.assert_called_once()
    mock_is_node_id_present_in_any_project_workbench.assert_called_once_with(
        mock.ANY, fake_running_service.node_uuid
    )
    mock_list_node_ids_in_project.assert_called_once_with(mock.ANY, project_id)

    expected_save_state = bool(
        node_exists and user_role > UserRole.GUEST and has_write_permission
    )
    if node_exists and user_role > UserRole.GUEST:
        mock_get_user_role.assert_called_once()
        mock_has_write_permission.assert_called_once_with(
            mock.ANY,
            project_id=fake_running_service.project_id,
            user_id=fake_running_service.user_id,
            permission="write",
        )
    elif node_exists:
        mock_get_user_role.assert_called_once()
        mock_has_write_permission.assert_not_called()
    else:
        mock_get_user_role.assert_not_called()
        mock_has_write_permission.assert_not_called()

    mock_stop_dynamic_service.assert_called_once_with(
        mock_app,
        dynamic_service_stop=DynamicServiceStop(
            user_id=fake_running_service.user_id,
            project_id=fake_running_service.project_id,
            node_id=fake_running_service.node_uuid,
            simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
            save_state=expected_save_state,
        ),
    )


@pytest.mark.parametrize("node_exists", [True], indirect=True)
@pytest.mark.parametrize(
    "get_user_role_error", [UserNotFoundError, ValueError], ids=str
)
async def test_remove_orphaned_services_inexisting_user_does_not_save_state(
    mock_app: mock.AsyncMock,
    mock_registry: mock.AsyncMock,
    mock_list_node_ids_in_project: mock.AsyncMock,
    mock_is_node_id_present_in_any_project_workbench: mock.AsyncMock,
    mock_list_dynamic_services: mock.AsyncMock,
    mock_stop_dynamic_service: mock.AsyncMock,
    mock_has_write_permission: mock.AsyncMock,
    mock_get_user_role: mock.AsyncMock,
    faker_dynamic_service_get: Callable[[], DynamicServiceGet],
    project_id: ProjectID,
    get_user_role_error: Exception,
):
    mock_get_user_role.side_effect = get_user_role_error
    fake_running_service = faker_dynamic_service_get()
    mock_list_dynamic_services.return_value = [fake_running_service]
    await remove_orphaned_services(mock_registry, mock_app)
    mock_list_dynamic_services.assert_called_once()
    mock_is_node_id_present_in_any_project_workbench.assert_called_once_with(
        mock.ANY, fake_running_service.node_uuid
    )
    mock_list_node_ids_in_project.assert_called_once_with(mock.ANY, project_id)
    mock_get_user_role.assert_called_once_with(mock_app, fake_running_service.user_id)
    mock_has_write_permission.assert_not_called()
    mock_stop_dynamic_service.assert_called_once_with(
        mock_app,
        dynamic_service_stop=DynamicServiceStop(
            user_id=fake_running_service.user_id,
            project_id=fake_running_service.project_id,
            node_id=fake_running_service.node_uuid,
            simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
            save_state=False,
        ),
    )


@pytest.mark.parametrize("node_exists", [False], indirect=True)
async def test_remove_orphaned_services_raises_exception_does_not_reraise(
    mock_app: mock.AsyncMock,
    mock_registry: mock.AsyncMock,
    mock_list_node_ids_in_project: mock.AsyncMock,
    mock_is_node_id_present_in_any_project_workbench: mock.AsyncMock,
    mock_list_dynamic_services: mock.AsyncMock,
    mock_stop_dynamic_service: mock.AsyncMock,
    faker_dynamic_service_get: Callable[[], DynamicServiceGet],
    caplog: pytest.LogCaptureFixture,
):
    error_msg = "Boom this is an error!"
    mock_stop_dynamic_service.side_effect = Exception(error_msg)
    fake_running_service = faker_dynamic_service_get()
    mock_list_dynamic_services.return_value = [fake_running_service]
    # this should not raise
    await remove_orphaned_services(mock_registry, mock_app)
    mock_list_dynamic_services.assert_called_once()
    mock_is_node_id_present_in_any_project_workbench.assert_called_once_with(
        mock.ANY, fake_running_service.node_uuid
    )
    # there should be error messages though
    error_records = [_ for _ in caplog.records if _.levelname == "ERROR"]
    assert len(error_records) == 1
    error_record = error_records[0]
    assert error_record.exc_text is not None
    assert error_msg in error_record.exc_text
