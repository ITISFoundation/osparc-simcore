# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio

import pytest
from celery.worker.worker import WorkController  # pylint: disable=no-name-in-module
from celery_library._task_manager import CeleryTaskManager
from celery_library.errors import TaskOrGroupNotFoundError, TransferableCeleryError
from faker import Faker
from models_library.celery import (
    OwnerMetadata,
    TaskExecutionMetadata,
    TaskState,
    TaskStatus,
    TaskUUID,
    Wildcard,
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
    fake_owner_metadata: OwnerMetadata,
):
    task_uuid = await task_manager.submit_task(
        TaskExecutionMetadata(
            name=fake_file_processor.__name__,
        ),
        owner_metadata=fake_owner_metadata,
        files=[f"file{n}" for n in range(5)],
    )

    await wait_for_task_success(task_manager, fake_owner_metadata, task_uuid)
    task_status = await task_manager.get_status(fake_owner_metadata, task_uuid)
    assert isinstance(task_status, TaskStatus)
    assert task_status.task_state == TaskState.SUCCESS
    assert (await task_manager.get_result(fake_owner_metadata, task_uuid)) == "archive.zip"


async def test_submitting_task_with_failure_results_with_error(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    task_uuid = await task_manager.submit_task(
        TaskExecutionMetadata(
            name=failure_task.__name__,
        ),
        owner_metadata=fake_owner_metadata,
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            raw_result = await task_manager.get_result(fake_owner_metadata, task_uuid)
            assert isinstance(raw_result, TransferableCeleryError)

    raw_result = await task_manager.get_result(fake_owner_metadata, task_uuid)
    assert f"{raw_result}" == "Something strange happened: BOOM!"


async def test_cancelling_a_running_task_aborts_and_deletes(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    task_uuid = await task_manager.submit_task(
        TaskExecutionMetadata(
            name=dreamer_task.__name__,
        ),
        owner_metadata=fake_owner_metadata,
    )

    await asyncio.sleep(3.0)

    await task_manager.cancel(fake_owner_metadata, task_uuid)

    with pytest.raises(TaskOrGroupNotFoundError):
        await task_manager.get_status(fake_owner_metadata, task_uuid)

    assert task_uuid not in await task_manager.list_tasks(fake_owner_metadata)


async def test_listing_task_uuids_contains_submitted_task(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    task_uuid = await task_manager.submit_task(
        TaskExecutionMetadata(
            name=dreamer_task.__name__,
        ),
        owner_metadata=fake_owner_metadata,
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            tasks = await task_manager.list_tasks(fake_owner_metadata)
            assert any(task.uuid == task_uuid for task in tasks)

    tasks = await task_manager.list_tasks(fake_owner_metadata)
    assert any(task.uuid == task_uuid for task in tasks)


async def test_filtering_listing_tasks(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
):
    class MyOwnerMetadata(OwnerMetadata):
        user_id: int
        product_name: str | Wildcard

    user_id = 42
    owner = "test-owner"
    expected_task_uuids: set[TaskUUID] = set()
    all_tasks: list[tuple[TaskUUID, MyOwnerMetadata]] = []

    try:
        for _ in range(5):
            owner_metadata = MyOwnerMetadata(user_id=user_id, product_name=_faker.word(), owner=owner)
            task_uuid = await task_manager.submit_task(
                TaskExecutionMetadata(
                    name=dreamer_task.__name__,
                ),
                owner_metadata=owner_metadata,
            )
            expected_task_uuids.add(task_uuid)
            all_tasks.append((task_uuid, owner_metadata))

        for _ in range(3):
            owner_metadata = MyOwnerMetadata(
                user_id=_faker.pyint(min_value=100, max_value=200),
                product_name=_faker.word(),
                owner=owner,
            )
            task_uuid = await task_manager.submit_task(
                TaskExecutionMetadata(
                    name=dreamer_task.__name__,
                ),
                owner_metadata=owner_metadata,
            )
            all_tasks.append((task_uuid, owner_metadata))

        search_owner_metadata = MyOwnerMetadata(
            user_id=user_id,
            product_name="*",
            owner=owner,
        )
        tasks = await task_manager.list_tasks(search_owner_metadata)
        assert expected_task_uuids == {task.uuid for task in tasks}
    finally:
        # clean up all tasks. this should ideally be done in the fixture
        for task_uuid, owner_metadata in all_tasks:
            await task_manager.cancel(owner_metadata, task_uuid)
