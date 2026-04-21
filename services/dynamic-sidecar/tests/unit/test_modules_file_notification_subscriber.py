# pylint:disable=redefined-outer-name

from unittest.mock import AsyncMock

import pytest
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_messages import (
    FileNotificationEventType,
    FileNotificationMessage,
)
from models_library.users import UserID
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.modules.file_notification_subscriber import (
    _handle_file_notification,
)


@pytest.fixture()
def project_id(faker: Faker) -> ProjectID:
    return faker.uuid4(cast_to=None)


@pytest.fixture()
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture()
def file_id(project_id: ProjectID, node_id: NodeID) -> str:
    return f"{project_id}/{node_id}/some-file.txt"


@pytest.fixture()
def user_id(faker: Faker) -> UserID:
    return faker.pyint(min_value=1)


@pytest.fixture()
def mock_notify_path_change(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_dynamic_sidecar.modules.file_notification_subscriber._notify_path_change",
        autospec=True,
    )


@pytest.mark.parametrize(
    "event_type",
    list(FileNotificationEventType),
)
async def test_handle_file_notification_calls_notify_path_change(
    mock_notify_path_change: AsyncMock,
    event_type: FileNotificationEventType,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    file_id: str,
):
    message = FileNotificationMessage(
        event_type=event_type,
        user_id=user_id,
        file_id=file_id,
        project_id=project_id,
        node_id=node_id,
    )
    data = message.body()

    result = await _handle_file_notification(None, data)

    assert result is True
    mock_notify_path_change.assert_awaited_once_with(app=None, event_type=event_type, path=file_id, recursive=False)


async def test_handle_file_notification_with_optional_ids(
    mock_notify_path_change: AsyncMock,
    file_id: str,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
):
    message = FileNotificationMessage(
        event_type=FileNotificationEventType.FILE_UPLOADED,
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        file_id=file_id,
    )
    data = message.body()

    result = await _handle_file_notification(None, data)

    assert result is True
    mock_notify_path_change.assert_awaited_once_with(
        app=None, event_type=FileNotificationEventType.FILE_UPLOADED, path=file_id, recursive=False
    )
