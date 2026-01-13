# pylint: disable=too-many-arguments

import datetime
import logging
from asyncio import CancelledError
from collections.abc import AsyncGenerator, Awaitable
from typing import Any, Final

from attr import dataclass
from celery_library.async_jobs import cancel_job, get_job_result, get_job_status, submit_job
from models_library.api_schemas_async_jobs.async_jobs import (
    AsyncJobId,
    AsyncJobStatus,
)
from models_library.api_schemas_async_jobs.exceptions import JobMissingError
from pydantic import NonNegativeInt
from tenacity import (
    AsyncRetrying,
    TryAgain,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_fixed,
    wait_random_exponential,
)

from servicelib.celery.task_manager import TaskManager

from ....celery.models import ExecutionMetadata, OwnerMetadata
from ....rabbitmq import RemoteMethodNotRegisteredError

_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 30
_DEFAULT_POLL_INTERVAL_S: Final[float] = 0.1

_logger = logging.getLogger(__name__)


_DEFAULT_RPC_RETRY_POLICY: dict[str, Any] = {
    "retry": retry_if_exception_type((RemoteMethodNotRegisteredError,)),
    "wait": wait_random_exponential(max=20),
    "stop": stop_after_attempt(30),
    "reraise": True,
    "before_sleep": before_sleep_log(_logger, logging.WARNING),
}


@retry(**_DEFAULT_RPC_RETRY_POLICY)
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
class AsyncJobComposedResult:
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


async def wait_and_get_result(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    job_id: AsyncJobId,
    stop_after: datetime.timedelta,
) -> AsyncGenerator[AsyncJobComposedResult]:
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
            yield AsyncJobComposedResult(job_status)

        # return the result
        if job_status:
            yield AsyncJobComposedResult(
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


async def submit_and_wait(
    task_manager: TaskManager,
    *,
    execution_metadata: ExecutionMetadata,
    owner_metadata: OwnerMetadata,
    stop_after: datetime.timedelta,
    **kwargs,
) -> AsyncGenerator[AsyncJobComposedResult]:
    async_job = None
    try:
        async_job = await submit_job(
            task_manager,
            execution_metadata=execution_metadata,
            owner_metadata=owner_metadata,
            **kwargs,
        )
    except (TimeoutError, CancelledError) as error:
        if async_job is not None:
            try:
                await cancel_job(
                    task_manager,
                    owner_metadata=owner_metadata,
                    job_id=async_job.job_id,
                )
            except Exception as exc:
                raise exc from error
        raise

    async for wait_and_ in wait_and_get_result(
        task_manager,
        job_id=async_job.job_id,
        owner_metadata=owner_metadata,
        stop_after=stop_after,
    ):
        yield wait_and_
