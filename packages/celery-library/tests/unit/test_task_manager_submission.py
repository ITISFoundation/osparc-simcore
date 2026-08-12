# pylint:disable=redefined-outer-name

from unittest.mock import AsyncMock, MagicMock

import pytest
from celery.exceptions import CeleryError, OperationalError  # type: ignore[import-untyped]
from celery_library import CeleryTaskManager
from celery_library.errors import TaskManagerError, TaskSubmissionError
from models_library.celery import OwnerMetadata, TaskExecutionMetadata


@pytest.fixture
def celery_app() -> MagicMock:
    return MagicMock()


@pytest.fixture
def task_store() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def task_manager(celery_app: MagicMock, task_store: AsyncMock) -> CeleryTaskManager:
    return CeleryTaskManager(_app=celery_app, _settings=MagicMock(), _task_store=task_store)


@pytest.mark.parametrize(
    "publish_error, expected_error",
    [
        (OperationalError("broker is unreachable"), TaskManagerError),
        (CeleryError("celery is unhappy"), TaskSubmissionError),
    ],
)
async def test_submit_task_cleans_up_when_publishing_fails(
    task_manager: CeleryTaskManager,
    celery_app: MagicMock,
    task_store: AsyncMock,
    fake_owner_metadata: OwnerMetadata,
    publish_error: Exception,
    expected_error: type[Exception],
):
    celery_app.send_task.side_effect = publish_error
    execution_metadata = TaskExecutionMetadata(name="a_task")

    with pytest.raises(expected_error):
        await task_manager.submit_task(execution_metadata, owner_metadata=fake_owner_metadata)

    task_store.create_task.assert_awaited_once()
    task_store.remove_task.assert_awaited_once()
