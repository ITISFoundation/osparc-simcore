import uuid
from unittest.mock import AsyncMock

import pytest
from models_library.rabbitmq_messages import (
    FileNotificationEventType,
    FileNotificationMessage,
)
from pytest_mock import MockerFixture
from simcore_service_storage.modules.rabbitmq import (
    _try_parse_uuid,
    post_file_notification,
)


@pytest.fixture()
def mock_app(mocker: MockerFixture) -> AsyncMock:
    app = AsyncMock()
    mock_client = AsyncMock()
    app.state.rabbitmq_client = mock_client
    return app


def test_try_parse_uuid():
    valid = uuid.uuid4()
    assert _try_parse_uuid(str(valid)) == valid
    assert _try_parse_uuid("api") is None
    assert _try_parse_uuid("not-a-uuid") is None


async def test_post_file_notification_standard_file_id(mock_app: AsyncMock):
    project_id = uuid.uuid4()
    node_id = uuid.uuid4()
    file_id = f"{project_id}/{node_id}/data.csv"

    await post_file_notification(
        mock_app,
        event_type=FileNotificationEventType.FILE_UPLOADED,
        user_id=42,
        file_id=file_id,
    )

    mock_client = mock_app.state.rabbitmq_client
    mock_client.publish.assert_called_once()
    call_args = mock_client.publish.call_args
    assert call_args[0][0] == FileNotificationMessage.get_channel_name()
    message = call_args[0][1]
    assert isinstance(message, FileNotificationMessage)
    assert message.event_type == FileNotificationEventType.FILE_UPLOADED
    assert message.user_id == 42
    assert message.project_id == project_id
    assert message.node_id == node_id
    assert message.file_id == file_id


async def test_post_file_notification_api_prefix_file_id(mock_app: AsyncMock):
    node_id = uuid.uuid4()
    file_id = f"api/{node_id}/data.csv"

    await post_file_notification(
        mock_app,
        event_type=FileNotificationEventType.FILE_DELETED,
        user_id=7,
        file_id=file_id,
    )

    mock_client = mock_app.state.rabbitmq_client
    mock_client.publish.assert_called_once()
    message = mock_client.publish.call_args[0][1]
    assert message.project_id is None
    assert message.node_id == node_id


async def test_post_file_notification_does_not_raise_on_publish_error(
    mock_app: AsyncMock,
):
    mock_app.state.rabbitmq_client.publish.side_effect = RuntimeError("connection lost")
    project_id = uuid.uuid4()
    node_id = uuid.uuid4()
    file_id = f"{project_id}/{node_id}/data.csv"

    # Should not raise
    await post_file_notification(
        mock_app,
        event_type=FileNotificationEventType.FILE_UPLOADED,
        user_id=1,
        file_id=file_id,
    )
