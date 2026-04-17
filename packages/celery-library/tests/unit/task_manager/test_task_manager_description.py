# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
from celery.worker.worker import WorkController  # pylint: disable=no-name-in-module
from models_library.celery import (
    GroupExecutionMetadata,
    GroupStatus,
    GroupTaskExecutionMetadata,
    TaskExecutionMetadata,
    TaskStatus,
)
from servicelib.celery.task_manager import TaskManager
from tenacity import AsyncRetrying

from .conftest import (
    _TENACITY_RETRY_PARAMS,
    dreamer_task,
    fake_file_processor,
    wait_for_task_success,
)


async def test_task_description_is_returned_in_progress_message(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    description = "Processing important files"
    task_uuid = await task_manager.submit_task(
        TaskExecutionMetadata(
            name=fake_file_processor.__name__,
            description=description,
        ),
        owner=fake_owner,
        user_id=fake_user_id,
        files=[f"file{n}" for n in range(3)],
    )
    # Check that the description appears in progress while task is running
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            status = await task_manager.get_status(task_uuid)
            assert isinstance(status, TaskStatus)
            assert status.progress_report.message is not None
            assert status.progress_report.message.description == description
    await wait_for_task_success(task_manager, task_uuid)
    # Check that the description is still present after completion
    final_status = await task_manager.get_status(task_uuid)
    assert isinstance(final_status, TaskStatus)
    assert final_status.progress_report.message is not None
    assert final_status.progress_report.message.description == description


async def test_task_without_description_has_no_message_in_progress(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    task_uuid = await task_manager.submit_task(
        TaskExecutionMetadata(
            name=dreamer_task.__name__,
        ),
        owner=fake_owner,
        user_id=fake_user_id,
    )
    # Check initial status has no message
    status = await task_manager.get_status(task_uuid)
    assert isinstance(status, TaskStatus)
    assert status.progress_report.message is None


async def test_group_description_is_returned_in_progress_message(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    description = "Processing files group"
    group_uuid, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="described_group",
            description=description,
            tasks=[
                (
                    GroupTaskExecutionMetadata(name=fake_file_processor.__name__),
                    {"files": [f"file{n}" for n in range(3)]},
                )
            ],
        ),
        owner=fake_owner,
        user_id=fake_user_id,
    )
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            status = await task_manager.get_status(group_uuid)
            assert isinstance(status, GroupStatus)
            assert status.progress_report.message is not None
            assert status.progress_report.message.description == description
    await wait_for_task_success(task_manager, task_uuids[0])
    final_status = await task_manager.get_status(group_uuid)
    assert isinstance(final_status, GroupStatus)
    assert final_status.progress_report.message is not None
    assert final_status.progress_report.message.description == description
