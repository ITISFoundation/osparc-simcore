# pylint: disable=redefined-outer-name

from typing import Final
from unittest import mock
from uuid import uuid4

import pytest
from models_library.celery import (
    GroupExecutionMetadata,
    GroupUUID,
    OwnerMetadata,
    TaskExecutionMetadata,
    TaskUUID,
)
from models_library.notifications import Channel
from pydantic import TypeAdapter
from servicelib.celery.async_jobs.notifications import (
    channel_from_notifications_queue_name,
    notifications_queue_name,
    submit_send_message_task,
    submit_send_messages_task,
)
from servicelib.celery.task_manager import TaskManager

_OWNER: Final[OwnerMetadata] = OwnerMetadata(owner="pytest")
_TASK_UUID: Final[TaskUUID] = TypeAdapter(TaskUUID).validate_python(str(uuid4()))
_GROUP_UUID: Final[GroupUUID] = TypeAdapter(GroupUUID).validate_python(str(uuid4()))


@pytest.fixture
def task_manager() -> mock.MagicMock:
    """Autospec'ed so submit calls are checked against the TaskManager protocol signature"""
    manager = mock.create_autospec(TaskManager, instance=True)
    manager.submit_task.return_value = _TASK_UUID
    manager.submit_group.return_value = (_GROUP_UUID, [_TASK_UUID])
    return manager


def test_notifications_queue_name_is_per_channel():
    assert notifications_queue_name(Channel.email) == "notifications-email"


@pytest.mark.parametrize(
    "channel",
    list(Channel),
)
def test_queue_name_round_trips_to_channel(channel: Channel):
    assert channel_from_notifications_queue_name(notifications_queue_name(channel)) == channel


@pytest.mark.parametrize("name", ["notifications", "celery", "cpu_bound", ""])
def test_channel_from_queue_rejects_non_channel_queues(name: str):
    with pytest.raises(ValueError, match="not a notifications per-channel queue"):
        channel_from_notifications_queue_name(name)


async def test_submit_send_message_task_routes_to_channel_queue(task_manager: mock.MagicMock):
    uuid, task_name = await submit_send_message_task(
        task_manager,
        owner_metadata=_OWNER,
        product_name="osparc",
        message={"channel": "email", "from": {}, "to": [], "content": {}},
    )

    assert uuid == _TASK_UUID
    assert task_name == "send_email_message_task"
    task_manager.submit_task.assert_awaited_once()
    execution_metadata = task_manager.submit_task.call_args.args[0]
    assert isinstance(execution_metadata, TaskExecutionMetadata)
    assert execution_metadata.name == "send_email_message_task"
    assert execution_metadata.queue == "notifications-email"


async def test_submit_send_messages_task_routes_group_tasks_to_channel_queue(task_manager: mock.MagicMock):
    group_uuid, task_uuids, task_name = await submit_send_messages_task(
        task_manager,
        owner_metadata=_OWNER,
        product_name="osparc",
        messages=[
            {"channel": "email", "from": {}, "to": [], "content": {}},
            {"channel": "email", "from": {}, "to": [], "content": {}},
        ],
    )

    assert group_uuid == _GROUP_UUID
    assert task_uuids == [_TASK_UUID]
    assert task_name == "send_email_message_task"
    task_manager.submit_group.assert_awaited_once()
    group_metadata = task_manager.submit_group.call_args.args[0]
    assert isinstance(group_metadata, GroupExecutionMetadata)
    assert len(group_metadata.tasks) == 2
    assert all(meta.queue == "notifications-email" for meta, _params in group_metadata.tasks)
