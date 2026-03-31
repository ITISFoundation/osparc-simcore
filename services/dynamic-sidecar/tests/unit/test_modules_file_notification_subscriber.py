# pylint:disable=redefined-outer-name

import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from faker import Faker
from models_library.rabbitmq_messages import (
    FileNotificationEventType,
    FileNotificationMessage,
)
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.modules.file_notification_subscriber import (
    _handle_file_notification,
)

faker = Faker()


@pytest.fixture()
def project_id() -> uuid.UUID:
    return faker.uuid4(cast_to=None)


@pytest.fixture()
def node_id() -> uuid.UUID:
    return faker.uuid4(cast_to=None)


@pytest.fixture()
def file_id(project_id: uuid.UUID, node_id: uuid.UUID) -> str:
    return f"{project_id}/{node_id}/some-file.txt"


@pytest.fixture()
def mock_notify_path_change(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_dynamic_sidecar.modules.file_notification_subscriber.container_extensions.notify_path_change",
        autospec=True,
    )


@pytest.mark.parametrize(
    "event_type",
    list(FileNotificationEventType),
)
async def test_handle_file_notification_calls_notify_path_change(
    mock_notify_path_change: AsyncMock,
    event_type: FileNotificationEventType,
    project_id: uuid.UUID,
    node_id: uuid.UUID,
    file_id: str,
):
    message = FileNotificationMessage(
        event_type=event_type,
        user_id=faker.pyint(min_value=1),
        file_id=file_id,
        project_id=project_id,
        node_id=node_id,
    )
    data = message.body()

    result = await _handle_file_notification(None, data)

    assert result is True
    mock_notify_path_change.assert_awaited_once_with(app=None, path=f"{Path(file_id).parent}", recursive=False)


async def test_handle_file_notification_with_optional_ids(
    mock_notify_path_change: AsyncMock,
    file_id: str,
):
    message = FileNotificationMessage(
        event_type=FileNotificationEventType.FILE_UPLOADED,
        user_id=faker.pyint(min_value=1),
        file_id=file_id,
    )
    data = message.body()

    result = await _handle_file_notification(None, data)

    assert result is True
    mock_notify_path_change.assert_awaited_once_with(app=None, path=f"{Path(file_id).parent}", recursive=False)
