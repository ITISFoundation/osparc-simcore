# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from typing import Final
from unittest import mock

import pytest
from faker import Faker
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.projects import ProjectID
from pytest_mock import MockerFixture
from simcore_service_webserver.garbage_collector._core_utils import (
    try_get_product_name,
)
from simcore_service_webserver.projects.exceptions import ProjectNotFoundError

MODULE_GC_CORE_UTILS: Final[str] = "simcore_service_webserver.garbage_collector._core_utils"


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def mock_app() -> mock.AsyncMock:
    return mock.AsyncMock()


@pytest.fixture
def mock_project_repo(mocker: MockerFixture) -> mock.AsyncMock:
    repo = mock.AsyncMock()
    mocker.patch(
        f"{MODULE_GC_CORE_UTILS}.ProjectDBAPI.get_from_app_context",
        return_value=repo,
    )
    return repo


@pytest.fixture
def mock_list_dynamic_services(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.patch(
        f"{MODULE_GC_CORE_UTILS}.dynamic_scheduler_service.list_dynamic_services",
        autospec=True,
        return_value=[],
    )


@pytest.fixture
def running_service() -> DynamicServiceGet:
    return DynamicServiceGet.model_validate(DynamicServiceGet.model_json_schema()["examples"][1])


async def test_returns_product_name_from_db_when_project_exists(
    mock_app: mock.AsyncMock,
    mock_project_repo: mock.AsyncMock,
    mock_list_dynamic_services: mock.AsyncMock,
    project_id: ProjectID,
):
    mock_project_repo.get_project_db.return_value = mock.Mock(product_name="s4l")

    product_name = await try_get_product_name(mock_app, project_id)

    assert product_name == "s4l"
    mock_project_repo.get_project_db.assert_awaited_once_with(project_id)
    # DB is authoritative: the dynamic-scheduler must not be queried
    mock_list_dynamic_services.assert_not_called()


@pytest.mark.parametrize("has_running_service", [True, False])
async def test_falls_back_to_dynamic_scheduler_when_project_not_in_db(
    mock_app: mock.AsyncMock,
    mock_project_repo: mock.AsyncMock,
    mock_list_dynamic_services: mock.AsyncMock,
    running_service: DynamicServiceGet,
    project_id: ProjectID,
    has_running_service: bool,
):
    mock_project_repo.get_project_db.side_effect = ProjectNotFoundError(project_uuid=project_id)
    mock_list_dynamic_services.return_value = [running_service] if has_running_service else []

    product_name = await try_get_product_name(mock_app, project_id)

    expected = running_service.product_name if has_running_service else None
    assert product_name == expected
    mock_list_dynamic_services.assert_awaited_once_with(mock_app, project_id=project_id)


async def test_returns_none_when_dynamic_scheduler_call_fails(
    mock_app: mock.AsyncMock,
    mock_project_repo: mock.AsyncMock,
    mock_list_dynamic_services: mock.AsyncMock,
    project_id: ProjectID,
):
    mock_project_repo.get_project_db.side_effect = ProjectNotFoundError(project_uuid=project_id)
    # a transient RPC/scheduler failure must not crash the garbage-collection cycle
    mock_list_dynamic_services.side_effect = RuntimeError("scheduler unreachable")

    product_name = await try_get_product_name(mock_app, project_id)

    assert product_name is None
