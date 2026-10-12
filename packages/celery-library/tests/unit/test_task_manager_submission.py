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
    task_manager_mock: CeleryTaskManager,
    celery_app_mock: MagicMock,
    task_store_mock: AsyncMock,
    fake_owner_metadata: OwnerMetadata,
    publish_error: Exception,
    expected_error: type[Exception],
):
    celery_app_mock.send_task.side_effect = publish_error
    execution_metadata = TaskExecutionMetadata(name="a_task")

    with pytest.raises(expected_error):
        await task_manager_mock.submit_task(execution_metadata, owner_metadata=fake_owner_metadata)

    task_store_mock.create_task.assert_awaited_once()
    task_store_mock.remove_task.assert_awaited_once()


async def test_submit_group_cleans_up_when_unexpected_error_occurs(
    task_manager_mock: CeleryTaskManager,
    task_store_mock: AsyncMock,
    fake_owner_metadata: OwnerMetadata,
):
    task_store_mock.create_task.side_effect = RuntimeError("unexpected metadata failure")
    execution_metadata = GroupExecutionMetadata(
        name="a_group",
        tasks=[(GroupTaskExecutionMetadata(name="a_task"), {})],
    )

    with pytest.raises(RuntimeError, match="unexpected metadata failure"):
        await task_manager_mock.submit_group(execution_metadata, owner_metadata=fake_owner_metadata)

    task_store_mock.create_task.assert_awaited_once()
    task_store_mock.remove_task.assert_awaited_once()
