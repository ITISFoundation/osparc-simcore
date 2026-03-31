# pylint: disable=redefined-outer-name

import uuid

import pytest
from faker import Faker
from models_library.rabbitmq_messages import (
    FileNotificationEventType,
    FileNotificationMessage,
)

faker = Faker()


@pytest.fixture()
def user_id() -> int:
    return faker.pyint(min_value=1)


@pytest.fixture()
def project_id() -> uuid.UUID:
    return faker.uuid4(cast_to=None)


@pytest.fixture()
def node_id() -> uuid.UUID:
    return faker.uuid4(cast_to=None)


@pytest.fixture()
def file_id(project_id: uuid.UUID, node_id: uuid.UUID) -> str:
    return f"{project_id}/{node_id}/some-file.txt"


def test_channel_name():
    assert FileNotificationMessage.get_channel_name() == "io.simcore.service.file-notifications"


@pytest.mark.parametrize("event_type", FileNotificationEventType)
def test_serialization_roundtrip(
    event_type: FileNotificationEventType,
    user_id: int,
    project_id: uuid.UUID,
    node_id: uuid.UUID,
    file_id: str,
):
    message = FileNotificationMessage(
        event_type=event_type,
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        file_id=file_id,
    )

    raw = message.body()
    restored = FileNotificationMessage.model_validate_json(raw)

    assert restored.event_type == event_type
    assert restored.user_id == user_id
    assert restored.project_id == project_id
    assert restored.node_id == node_id
    assert restored.file_id == file_id
    assert restored.created_at == message.created_at


def test_routing_key_format(
    user_id: int,
    project_id: uuid.UUID,
    node_id: uuid.UUID,
    file_id: str,
):
    message = FileNotificationMessage(
        event_type=FileNotificationEventType.FILE_UPLOADED,
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        file_id=file_id,
    )

    routing_key = message.routing_key()
    assert routing_key == f"{project_id}.{node_id}"


def test_optional_project_and_node_id(user_id: int):
    file_id = f"api/{uuid.uuid4()}/some-file.txt"
    message = FileNotificationMessage(
        event_type=FileNotificationEventType.FILE_UPLOADED,
        user_id=user_id,
        file_id=file_id,
    )

    assert message.project_id is None
    assert message.node_id is None
    assert message.routing_key() == "None.None"

    raw = message.body()
    restored = FileNotificationMessage.model_validate_json(raw)
    assert restored.project_id is None
    assert restored.node_id is None


def test_all_event_types_exist():
    assert set(FileNotificationEventType) == {
        FileNotificationEventType.FILE_UPLOADED,
        FileNotificationEventType.FILE_DELETED,
        FileNotificationEventType.FILE_MOVED,
    }
