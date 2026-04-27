# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio

import pytest
from celery.worker.worker import WorkController  # pylint: disable=no-name-in-module
from celery_library._task_manager import CeleryTaskManager
from celery_library.errors import TaskNotFoundError, TransferableCeleryError
from faker import Faker
from models_library.celery import (
    TaskExecutionMetadata,
    TaskID,
    TaskState,
    TaskStatus,
)
from servicelib.celery.task_manager import TaskManager
from tenacity import AsyncRetrying

from .conftest import (
    _TENACITY_RETRY_PARAMS,
    dreamer_task,
    failure_task,
    fake_file_processor,
    wait_for_task_success,
)

_faker = Faker()


async def test_submitting_task_calling_async_function_results_with_success_state(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    task_uuid = await task_manager.submit_task(
        TaskExecutionMetadata(
            name=fake_file_processor.__name__,
        ),
        owner=fake_owner,
        user_id=fake_user_id,
        files=[f"file{n}" for n in range(5)],
    )

    await wait_for_task_success(task_manager, task_uuid)
    task_status = await task_manager.get_status(task_uuid)
    assert isinstance(task_status, TaskStatus)
    assert task_status.task_state == TaskState.SUCCESS
    assert (await task_manager.get_result(task_uuid)) == "archive.zip"


async def test_submitting_task_with_failure_results_with_error(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    task_uuid = await task_manager.submit_task(
        TaskExecutionMetadata(
            name=failure_task.__name__,
        ),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            raw_result = await task_manager.get_result(task_uuid)
            assert isinstance(raw_result, TransferableCeleryError)

    raw_result = await task_manager.get_result(task_uuid)
    assert f"{raw_result}" == "Something strange happened: BOOM!"


async def test_cancelling_a_running_task_aborts_and_deletes(
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

    await asyncio.sleep(3.0)

    await task_manager.cancel(task_uuid)

    with pytest.raises(TaskNotFoundError):
        await task_manager.get_status(task_uuid)

    assert task_uuid not in await task_manager.list_tasks(owner=fake_owner, user_id=fake_user_id)


async def test_listing_task_uuids_contains_submitted_task(
    task_manager: CeleryTaskManager,
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

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            tasks = await task_manager.list_tasks(owner=fake_owner, user_id=fake_user_id)
            assert any(task.uuid == task_uuid for task in tasks)

    tasks = await task_manager.list_tasks(owner=fake_owner, user_id=fake_user_id)
    assert any(task.uuid == task_uuid for task in tasks)


async def test_filtering_listing_tasks(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
):
    user_id = _faker.pyint(min_value=1000, max_value=9999)
    owner = f"test-owner-{_faker.uuid4()}"
    expected_task_uuids: set[TaskID] = set()
    all_task_uuids: list[TaskID] = []

    try:
        for _ in range(5):
            task_uuid = await task_manager.submit_task(
                TaskExecutionMetadata(
                    name=dreamer_task.__name__,
                ),
                owner=owner,
                user_id=user_id,
                product_name=_faker.word(),
            )
            expected_task_uuids.add(task_uuid)
            all_task_uuids.append(task_uuid)

        for _ in range(3):
            task_uuid = await task_manager.submit_task(
                TaskExecutionMetadata(
                    name=dreamer_task.__name__,
                ),
                owner=owner,
                user_id=_faker.pyint(min_value=100, max_value=200),
                product_name=_faker.word(),
            )
            all_task_uuids.append(task_uuid)

        # Query by owner + user_id only (product_name=None acts as wildcard)
        tasks = await task_manager.list_tasks(owner=owner, user_id=user_id)
        assert expected_task_uuids == {task.uuid for task in tasks}
    finally:
        for task_uuid in all_task_uuids:
            await task_manager.cancel(task_uuid)
