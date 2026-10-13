from unittest.mock import AsyncMock, MagicMock

import pytest
from celery.exceptions import CeleryError, OperationalError  # type: ignore[import-untyped]
from celery_library import CeleryTaskManager
from celery_library.errors import TaskManagerError, TaskSubmissionError
from models_library.celery import (
    GroupExecutionMetadata,
    GroupTaskExecutionMetadata,
    OwnerMetadata,
    TaskExecutionMetadata,
)


@pytest.mark.parametrize(
    "publish_error, expected_error",
    [
        (OperationalError("broker is unreachable"), TaskManagerError),
        (CeleryError("celery is unhappy"), TaskSubmissionError),
        (RuntimeError("unexpected publish failure"), RuntimeError),
    ],
)
async def test_submit_task_cleans_up_when_publishing_fails(
    mocked_task_manager: CeleryTaskManager,
    mocked_celery_app: MagicMock,
    mocked_task_store: AsyncMock,
    fake_owner_metadata: OwnerMetadata,
    publish_error: Exception,
    expected_error: type[Exception],
):
    mocked_celery_app.send_task.side_effect = publish_error
    execution_metadata = TaskExecutionMetadata(name="a_task")

    with pytest.raises(expected_error):
        await mocked_task_manager.submit_task(execution_metadata, owner_metadata=fake_owner_metadata)

    mocked_task_store.create_task.assert_awaited_once()
    mocked_task_store.remove_task.assert_awaited_once()


async def test_submit_group_cleans_up_when_unexpected_error_occurs(
    mocked_task_manager: CeleryTaskManager,
    mocked_task_store: AsyncMock,
    fake_owner_metadata: OwnerMetadata,
):
    mocked_task_store.create_task.side_effect = RuntimeError("unexpected metadata failure")
    execution_metadata = GroupExecutionMetadata(
        name="a_group",
        tasks=[(GroupTaskExecutionMetadata(name="a_task"), {})],
    )

    with pytest.raises(RuntimeError, match="unexpected metadata failure"):
        await mocked_task_manager.submit_group(execution_metadata, owner_metadata=fake_owner_metadata)

    mocked_task_store.create_task.assert_awaited_once()
    mocked_task_store.remove_task.assert_awaited_once()
