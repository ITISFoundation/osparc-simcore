# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from unittest.mock import AsyncMock

import pytest
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_messages import (
    FileNotificationEventType,
    FileNotificationMessage,
)
from pytest_mock import MockerFixture
from simcore_service_storage.modules.rabbitmq import post_file_notification


@pytest.fixture()
def mock_app(mocker: MockerFixture) -> AsyncMock:
    app = AsyncMock()
    mock_client = AsyncMock()
    app.state.rabbitmq_client = mock_client
    return app


@pytest.fixture()
def project_id(faker: Faker) -> ProjectID:
    return faker.uuid4(cast_to=None)


@pytest.fixture()
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


async def test_post_file_notification_standard_file_id(mock_app: AsyncMock, project_id: ProjectID, node_id: NodeID):
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


@pytest.mark.parametrize(
    "file_id",
    [
        "exports/path/{uuid}.zip",
        "api/{uuid}/{uuid}/path/data.csv",
    ],
)
async def test_post_file_notification_skipped_prefeixes(mock_app: AsyncMock, file_id: str, faker: Faker):
    await post_file_notification(
        mock_app,
        event_type=FileNotificationEventType.FILE_DELETED,
        user_id=7,
        file_id=file_id.format(uuid=faker.uuid4()),
    )

    mock_client = mock_app.state.rabbitmq_client
    mock_client.publish.assert_not_called()


async def test_post_file_notification_does_not_raise_on_publish_error(
    mock_app: AsyncMock, project_id: ProjectID, node_id: NodeID
):
    mock_app.state.rabbitmq_client.publish.side_effect = RuntimeError("connection lost")
    file_id = f"{project_id}/{node_id}/data.csv"

    # Should not raise
    await post_file_notification(
        mock_app,
        event_type=FileNotificationEventType.FILE_UPLOADED,
        user_id=1,
        file_id=file_id,
    )
