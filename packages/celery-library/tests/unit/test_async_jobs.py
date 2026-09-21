# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import pickle
from collections.abc import Callable
from datetime import timedelta
from enum import StrEnum
from typing import Any
from unittest.mock import MagicMock

import pytest
from celery import Celery, Task
from celery.worker.worker import WorkController
from celery_library.async_jobs import cancel_job, get_job_result, get_job_status, list_jobs, submit_job
from celery_library.task import register_task
from common_library.errors_classes import OsparcErrorMixin
from faker import Faker
from models_library.api_schemas_async_jobs.async_jobs import (
    AsyncJobId,
)
from models_library.api_schemas_async_jobs.exceptions import (
    JobError,
    JobMissingError,
)
from models_library.celery import OwnerMetadata, TaskExecutionMetadata, TaskKey
from servicelib.celery.task_manager import TaskManager
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)


class AccessRightError(OsparcErrorMixin, RuntimeError):
    msg_template: str = "User {user_id} does not have access to file {file_id} with location {location_id}"


@pytest.fixture
def owner_metadata(faker: Faker) -> OwnerMetadata:
    return OwnerMetadata(
        user_id=faker.pyint(min_value=1),
        product_name=faker.word(),
        owner="pytest_client",
    )


class Action(StrEnum):
    ECHO = "ECHO"
    RAISE = "RAISE"
    SLEEP = "SLEEP"


async def _process_action(action: str, payload: Any) -> Any:
    match action:
        case Action.ECHO:
            return payload
        case Action.RAISE:
            raise pickle.loads(payload)  # noqa: S301
        case Action.SLEEP:
            await asyncio.sleep(payload)
    return None


# records every task execution attempt (incl. retries) so tests can assert on retry counts
_task_execution_mock = MagicMock()


def sync_job(task: Task, task_key: TaskKey, action: Action, payload: Any) -> Any:
    _ = task_key
    _task_execution_mock()
    return asyncio.run(_process_action(action, payload))


async def async_job(task: Task, task_key: TaskKey, action: Action, payload: Any) -> Any:
    _ = task_key
    _task_execution_mock()
    return await _process_action(action, payload)


NO_RETRY_SYNC_JOB_NAME = f"{sync_job.__name__}_no_retry"
NO_RETRY_ASYNC_JOB_NAME = f"{async_job.__name__}_no_retry"


#################################


@pytest.fixture
def task_execution_mock() -> MagicMock:
    _task_execution_mock.reset_mock()
    return _task_execution_mock


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    def _(celery_app: Celery) -> None:
        register_task(
            celery_app,
            sync_job,
            max_retries=1,
            delay_between_retries=timedelta(seconds=1),
            dont_autoretry_for=(AccessRightError,),
        )
        register_task(
            celery_app,
            async_job,
            max_retries=1,
            delay_between_retries=timedelta(seconds=1),
            dont_autoretry_for=(AccessRightError,),
        )
        # long delay so a leaked retry would be caught by the short polling window used in tests
        register_task(
            celery_app,
            sync_job,
            task_name=NO_RETRY_SYNC_JOB_NAME,
            max_retries=0,
            delay_between_retries=timedelta(seconds=5),
        )
        register_task(
            celery_app,
            async_job,
            task_name=NO_RETRY_ASYNC_JOB_NAME,
            max_retries=0,
            delay_between_retries=timedelta(seconds=5),
        )

    return _


async def _wait_for_job(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    job_id: AsyncJobId,
    stop_after: timedelta = timedelta(seconds=5),
) -> None:
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(stop_after.total_seconds()),
        wait=wait_fixed(0.1),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            status = await get_job_status(
                task_manager,
                owner_metadata=owner_metadata,
                job_id=job_id,
            )
            assert status.done is True, "Please check logs above, something went wrong with task execution"


@pytest.mark.parametrize(
    "execution_metadata",
    [
        TaskExecutionMetadata(name=sync_job.__name__),
        TaskExecutionMetadata(name=async_job.__name__),
    ],
)
@pytest.mark.parametrize(
    "payload",
    [
        None,
        1,
        "a_string",
        {"a": "dict"},
        ["a", "list"],
        {"a", "set"},
    ],
)
async def test_async_jobs_workflow(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
    execution_metadata: TaskExecutionMetadata,
    owner_metadata: OwnerMetadata,
    payload: Any,
):
    async_job = await submit_job(
        task_manager,
        execution_metadata=execution_metadata,
        owner_metadata=owner_metadata,
        action=Action.ECHO,
        payload=payload,
    )

    jobs = await list_jobs(
        task_manager,
        owner_metadata=owner_metadata,
    )
    assert len(jobs) > 0

    await _wait_for_job(
        task_manager,
        owner_metadata=owner_metadata,
        job_id=async_job.job_id,
    )

    async_job_result = await get_job_result(
        task_manager,
        owner_metadata=owner_metadata,
        job_id=async_job.job_id,
    )
    assert async_job_result.result == payload


@pytest.mark.parametrize(
    "execution_metadata",
    [
        TaskExecutionMetadata(name=async_job.__name__),
    ],
)
async def test_async_jobs_cancel(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
    execution_metadata: TaskExecutionMetadata,
    owner_metadata: OwnerMetadata,
):
    async_job = await submit_job(
        task_manager,
        execution_metadata=execution_metadata,
        owner_metadata=owner_metadata,
        action=Action.SLEEP,
        payload=60 * 10,  # test hangs if not cancelled properly
    )

    await cancel_job(
        task_manager,
        owner_metadata=owner_metadata,
        job_id=async_job.job_id,
    )

    jobs = await list_jobs(
        task_manager,
        owner_metadata=owner_metadata,
    )
    assert async_job.job_id not in [job.job_id for job in jobs]

    with pytest.raises(JobMissingError):
        await get_job_status(
            task_manager,
            owner_metadata=owner_metadata,
            job_id=async_job.job_id,
        )

    with pytest.raises(JobMissingError):
        await get_job_result(
            task_manager,
            owner_metadata=owner_metadata,
            job_id=async_job.job_id,
        )


@pytest.mark.parametrize(
    "execution_metadata",
    [
        TaskExecutionMetadata(name=sync_job.__name__),
        TaskExecutionMetadata(name=async_job.__name__),
    ],
)
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(Exception("generic error"), id="generic-error"),
        pytest.param(
            AccessRightError(user_id=1, file_id="fake_key", location_id=0),
            id="custom-osparc-error",
        ),
    ],
)
async def test_async_jobs_raises(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
    execution_metadata: TaskExecutionMetadata,
    owner_metadata: OwnerMetadata,
    error: Exception,
):
    async_job = await submit_job(
        task_manager,
        execution_metadata=execution_metadata,
        owner_metadata=owner_metadata,
        action=Action.RAISE,
        payload=pickle.dumps(error),
    )

    await _wait_for_job(
        task_manager,
        owner_metadata=owner_metadata,
        job_id=async_job.job_id,
        stop_after=timedelta(minutes=1),
    )

    with pytest.raises(JobError) as exc:
        await get_job_result(
            task_manager,
            owner_metadata=owner_metadata,
            job_id=async_job.job_id,
        )
    assert exc.value.exc_type == type(error).__name__
    assert exc.value.exc_msg == f"{error}"


@pytest.mark.parametrize(
    "execution_metadata",
    [
        TaskExecutionMetadata(name=NO_RETRY_SYNC_JOB_NAME),
        TaskExecutionMetadata(name=NO_RETRY_ASYNC_JOB_NAME),
    ],
)
async def test_async_jobs_max_retries_zero_never_retries(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
    execution_metadata: TaskExecutionMetadata,
    owner_metadata: OwnerMetadata,
    task_execution_mock: MagicMock,
):
    error = Exception("generic error")
    async_job = await submit_job(
        task_manager,
        execution_metadata=execution_metadata,
        owner_metadata=owner_metadata,
        action=Action.RAISE,
        payload=pickle.dumps(error),
    )

    # registered with a 5s delay_between_retries: completing well before that
    # proves no retry was ever scheduled
    await _wait_for_job(
        task_manager,
        owner_metadata=owner_metadata,
        job_id=async_job.job_id,
        stop_after=timedelta(seconds=2),
    )

    with pytest.raises(JobError) as exc:
        await get_job_result(
            task_manager,
            owner_metadata=owner_metadata,
            job_id=async_job.job_id,
        )
    assert exc.value.exc_type == type(error).__name__
    assert exc.value.exc_msg == f"{error}"

    # should only ever be called once when retry is disabled
    assert task_execution_mock.call_count == 1
