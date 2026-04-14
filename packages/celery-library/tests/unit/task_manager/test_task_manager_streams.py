# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from celery.worker.worker import WorkController  # pylint: disable=no-name-in-module
from celery_library._task_manager import CeleryTaskManager
from celery_library.errors import TaskOrGroupNotFoundError
from faker import Faker
from models_library.celery import (
    OwnerMetadata,
    TaskExecutionMetadata,
    TaskStreamItem,
    TaskUUID,
)
from pydantic import TypeAdapter
from tenacity import AsyncRetrying

from .conftest import (
    _TENACITY_RETRY_PARAMS,
    streaming_results_task,
    wait_for_task_success,
)

_faker = Faker()


async def test_push_task_result_streams_data_during_execution(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    num_results = 3

    task_uuid = await task_manager.submit_task(
        TaskExecutionMetadata(
            name=streaming_results_task.__name__,
            ephemeral=False,  # Keep task available after completion for result pulling
        ),
        owner_metadata=fake_owner_metadata,
        num_results=num_results,
    )

    # Pull results while task is running, retry until is_done is True
    results = []
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            result, is_done, _ = await task_manager.pull_task_stream_items(fake_owner_metadata, task_uuid, limit=10)
            results.extend(result)
            assert is_done

    # Should have at least some results streamed
    assert results == [TaskStreamItem(data=f"result-{i}") for i in range(num_results)]

    # Wait for task completion
    await wait_for_task_success(task_manager, fake_owner_metadata, task_uuid)

    # Final task result should be available
    final_result = await task_manager.get_result(fake_owner_metadata, task_uuid)
    assert final_result == f"completed-{num_results}-results"

    # After task completion, try to pull any remaining results
    remaining_results, is_done, _ = await task_manager.pull_task_stream_items(fake_owner_metadata, task_uuid, limit=10)
    assert remaining_results == []
    assert is_done


async def test_pull_task_stream_items_with_limit(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    # Submit task with fewer results to make it more predictable
    task_uuid = await task_manager.submit_task(
        TaskExecutionMetadata(
            name=streaming_results_task.__name__,
            ephemeral=False,  # Keep task available after completion for result pulling
        ),
        owner_metadata=fake_owner_metadata,
        num_results=5,
    )

    # Wait for task to complete
    await wait_for_task_success(task_manager, fake_owner_metadata, task_uuid)

    # Pull all results in one go to avoid consumption issues
    all_results, is_done_final, _last_update_final = await task_manager.pull_task_stream_items(
        fake_owner_metadata,
        task_uuid,
        limit=20,  # High limit to get all items
    )

    assert all_results is not None

    assert len(all_results) == 5  # Can't have more than what was created
    assert is_done_final

    # Verify result format for any results we got
    for result in all_results:
        assert result.data.startswith("result-")


async def test_pull_task_stream_items_from_nonexistent_task_raises_error(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    fake_task_uuid = TypeAdapter(TaskUUID).validate_python(_faker.uuid4())

    with pytest.raises(TaskOrGroupNotFoundError):
        await task_manager.pull_task_stream_items(fake_owner_metadata, fake_task_uuid)


async def test_push_task_stream_items_to_nonexistent_task_raises_error(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
):
    not_existing_task_id = "not_existing"

    with pytest.raises(TaskOrGroupNotFoundError):
        await task_manager.push_task_stream_items(not_existing_task_id, TaskStreamItem(data="some-result"))
