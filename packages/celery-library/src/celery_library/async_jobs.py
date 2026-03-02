# pylint: disable=unused-argument

import datetime
import logging
from asyncio import CancelledError
from collections.abc import AsyncGenerator, Awaitable
from dataclasses import dataclass
from typing import Any, Final

from models_library.api_schemas_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobId,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.api_schemas_async_jobs.exceptions import (
    JobError,
    JobMissingError,
    JobNotDoneError,
    JobSchedulerError,
)
from servicelib.celery.models import ExecutionMetadata, OwnerMetadata, TaskState
from servicelib.celery.task_manager import TaskManager
from servicelib.logging_utils import log_catch
from tenacity import (
    AsyncRetrying,
    TryAgain,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

from .errors import (
    TaskManagerError,
    TaskNotFoundError,
    TransferableCeleryError,
    decode_celery_transferable_error,
)

_logger: Final[logging.Logger] = logging.getLogger(__name__)

_DEFAULT_POLL_INTERVAL_S: Final[float] = 0.1


async def cancel_job(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    job_id: AsyncJobId,
) -> None:
    try:
        await task_manager.cancel_task(
            owner_metadata=owner_metadata,
            task_uuid=job_id,
        )
    except TaskNotFoundError as exc:
        raise JobMissingError(job_id=job_id) from exc
    except TaskManagerError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc


async def get_job_result(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    job_id: AsyncJobId,
) -> AsyncJobResult:
    assert task_manager  # nosec
    assert job_id  # nosec
    assert owner_metadata  # nosec

    try:
        task_status = await task_manager.get_task_status(
            owner_metadata=owner_metadata,
            task_uuid=job_id,
        )
        if not task_status.is_done:
            raise JobNotDoneError(job_id=job_id)
        task_result = await task_manager.get_task_result(
            owner_metadata=owner_metadata,
            task_uuid=job_id,
        )
    except TaskNotFoundError as exc:
        raise JobMissingError(job_id=job_id) from exc
    except TaskManagerError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    if task_status.task_state == TaskState.FAILURE:
        # fallback exception to report
        exc_type = type(task_result).__name__
        exc_msg = f"{task_result}"

        # try to recover the original error
        exception = None
        with log_catch(_logger, reraise=False):
            assert isinstance(task_result, TransferableCeleryError)  # nosec
            exception = decode_celery_transferable_error(task_result)
            exc_type = type(exception).__name__
            exc_msg = f"{exception}"

        if exception is None:
            _logger.warning("Was not expecting '%s': '%s'", exc_type, exc_msg)

        # NOTE: cannot transfer original exception since this will not be able to be serialized
        # outside of storage
        raise JobError(job_id=job_id, exc_type=exc_type, exc_msg=exc_msg)

    return AsyncJobResult(result=task_result)


async def get_job_status(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    job_id: AsyncJobId,
) -> AsyncJobStatus:
    try:
        task_status = await task_manager.get_status(
            owner_metadata=owner_metadata,
            task_or_group_uuid=job_id,
        )
    except TaskNotFoundError as exc:
        raise JobMissingError(job_id=job_id) from exc
    except TaskManagerError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    return AsyncJobStatus(
        job_id=job_id,
        progress=task_status.progress_report,
        done=task_status.is_done,
    )


async def list_jobs(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
) -> list[AsyncJobGet]:
    assert task_manager  # nosec
    try:
        tasks = await task_manager.list_tasks(
            owner_metadata=owner_metadata,
        )
    except TaskManagerError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    return [AsyncJobGet(job_id=task.uuid, job_name=task.metadata.name) for task in tasks]


async def submit_job(
    task_manager: TaskManager,
    *,
    execution_metadata: ExecutionMetadata,
    owner_metadata: OwnerMetadata,
    **kwargs,
) -> AsyncJobGet:
    task_id = await task_manager.submit_task(
        execution_metadata=execution_metadata,
        owner_metadata=owner_metadata,
        **kwargs,
    )
    return AsyncJobGet(job_id=task_id, job_name=execution_metadata.name)


async def _wait_for_completion(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    job_id: AsyncJobId,
    stop_after: datetime.timedelta,
) -> AsyncGenerator[AsyncJobStatus]:
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_delay(stop_after.total_seconds()),
            reraise=True,
            retry=retry_if_exception_type((TryAgain, JobMissingError)),
            before_sleep=before_sleep_log(_logger, logging.DEBUG),
            wait=wait_fixed(_DEFAULT_POLL_INTERVAL_S),
        ):
            with attempt:
                job_status = await get_job_status(
                    task_manager,
                    owner_metadata=owner_metadata,
                    job_id=job_id,
                )
                yield job_status
                if not job_status.done:
                    msg = f"{job_status.job_id=}: '{job_status.progress=}'"
                    raise TryAgain(msg)  # noqa: TRY301

    except TryAgain as exc:
        # this is a timeout
        msg = f"Async job {job_id=}, timed-out after {stop_after.total_seconds()}s"
        raise TimeoutError(msg) from exc


@dataclass(frozen=True)
class AsyncJobResultUpdate:
    status: AsyncJobStatus
    _result: Awaitable[Any] | None = None

    @property
    def done(self) -> bool:
        return self._result is not None

    async def result(self) -> Any:
        if not self._result:
            msg = "No result ready!"
            raise ValueError(msg)
        return await self._result


async def wait_and_get_job_result(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    job_id: AsyncJobId,
    stop_after: datetime.timedelta,
) -> AsyncGenerator[AsyncJobResultUpdate]:
    """when a job is already submitted this will wait for its completion
    and return the composed result"""
    try:
        job_status = None
        async for job_status in _wait_for_completion(
            task_manager,
            job_id=job_id,
            owner_metadata=owner_metadata,
            stop_after=stop_after,
        ):
            assert job_status is not None  # nosec
            yield AsyncJobResultUpdate(job_status)

        # return the result
        if job_status:
            yield AsyncJobResultUpdate(
                job_status,
                get_job_result(
                    task_manager,
                    owner_metadata=owner_metadata,
                    job_id=job_id,
                ),
            )
    except (TimeoutError, CancelledError) as error:
        try:
            await cancel_job(
                task_manager,
                owner_metadata=owner_metadata,
                job_id=job_id,
            )
        except Exception as exc:
            raise exc from error  # NOSONAR
        raise


async def submit_job_and_wait(
    task_manager: TaskManager,
    *,
    execution_metadata: ExecutionMetadata,
    owner_metadata: OwnerMetadata,
    stop_after: datetime.timedelta,
    **kwargs,
) -> AsyncGenerator[AsyncJobResultUpdate]:
    async_job = None
    try:
        async_job = await submit_job(
            task_manager,
            execution_metadata=execution_metadata,
            owner_metadata=owner_metadata,
            **kwargs,
        )
    except (TimeoutError, CancelledError):
        if async_job is not None:
            await cancel_job(
                task_manager,
                owner_metadata=owner_metadata,
                job_id=async_job.job_id,
            )
        raise

    async for wait_and_ in wait_and_get_job_result(
        task_manager,
        job_id=async_job.job_id,
        owner_metadata=owner_metadata,
        stop_after=stop_after,
    ):
        yield wait_and_
