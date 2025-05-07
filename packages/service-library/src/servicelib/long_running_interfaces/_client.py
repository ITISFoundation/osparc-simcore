import asyncio
import logging
from datetime import timedelta
from typing import Annotated, Any, Final, TypeVar
from uuid import uuid4

from pydantic import ConfigDict, Field, NonNegativeInt, validate_call
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings

from ._errors import (
    AlreadyStartedError,
    FinishedWithError,
    TimedOutError,
    UnexpectedNoMoreRetryAttemptsError,
    UnexpectedResultTypeError,
    UnexpectedStatusError,
)
from ._models import (
    CorrelationID,
    JobStatus,
    JobUniqueId,
    LongRunningNamespace,
    RemoteHandlerName,
    ResultModel,
    ScheduleModel,
    StartParams,
    UniqueIdModel,
)
from ._redis import ClientStoreInterface
from ._rpc.client import ClientRPCInterface

_logger = logging.getLogger(__name__)

_UNIQUE_CORRELATION_ID: Final[CorrelationID] = "UNIQUE"
_SLEEP_BEFORE_RETRY: Final[timedelta] = timedelta(seconds=1)
_STATUS_POLL_RATE: Final[timedelta] = timedelta(seconds=1)

ResultType = TypeVar("ResultType")


def _get_correlation_id(*, is_unique: bool) -> CorrelationID:
    return f"{uuid4()}" if is_unique else _UNIQUE_CORRELATION_ID


class Client:
    """Client for managing and interacting with long-running remote jobs.

    This class provides a resilient interface to schedule, track, and retrieve results from
    long-running jobs executing on remote servers. It implements fault tolerance through:

    1. Automatic job tracking in Redis to preserve state across client restarts
    2. Configurable retry mechanism for handling transient errors
    3. Timeout management to prevent indefinite waiting
    4. Correlation ID system to deduplicate or uniquely identify job requests

    Internally, the client relies on two main components:
    - RPC Interface: Handles communication with remote job handlers via RabbitMQ
    - Store Interface: Manages job state persistence in Redis

    The client workflow:
    1. Generate a unique or reusable job ID based on parameters
    2. Track the job in Redis with remaining retry attempts
    3. Start the job on the remote server if not already running
    4. Poll for job status until completion or failure
    5. On failure, retry the job if attempts remain
    6. On success, verify result type and return data
    7. Clean up resources on both client and server side

    This resilient approach ensures jobs can survive temporary network issues,
    service restarts, and transient failures in the distributed system.
    """

    def __init__(
        self,
        rabbit_settings: RabbitSettings,
        redis_settings: RedisSettings,
        long_running_namespace: LongRunningNamespace,
    ) -> None:
        self._rpc_interface = ClientRPCInterface(
            rabbit_settings, long_running_namespace
        )
        self._store_interface = ClientStoreInterface(
            redis_settings, long_running_namespace
        )

    async def setup(self) -> None:
        await self._store_interface.setup()
        await self._rpc_interface.setup()

    async def teardown(self) -> None:
        await self._rpc_interface.teardown()
        await self._store_interface.teardown()

    async def _track_job_if_not_tracked(
        self,
        name: RemoteHandlerName,
        unique_id: JobUniqueId,
        correlation_id: CorrelationID,
        params: StartParams,
        retry_count: NonNegativeInt,
        timeout: timedelta,  # noqa: ASYNC109
    ) -> None:
        # keep track of the job clinet side
        schedule_data = await self._store_interface.get(unique_id)
        if schedule_data is None:
            await self._store_interface.set(
                unique_id,
                ScheduleModel(
                    name=name,
                    correlation_id=correlation_id,
                    params=params,
                    remaining_attempts=retry_count,
                ),
                expire=timeout,
            )

    async def _decrease_remaining_attempts_or_raise(
        self,
        unique_id: JobUniqueId,
        retry_count: NonNegativeInt,
        last_result: ResultModel | None,
    ) -> None:
        async with self._store_interface.auto_save_get(unique_id) as schedule_data:
            schedule_data.remaining_attempts -= 1

        # are there any attempts left?
        if (await self._store_interface.get_existing(unique_id)).remaining_attempts < 0:
            remaining_attempts = await self._format_remaining_attempts(
                unique_id, retry_count
            )
            # report remote error if there is one
            if last_result and last_result.error is not None:
                _logger.warning(
                    "unique_id='%s', finished with error from remote: %s='%s'\n%s",
                    unique_id,
                    last_result.error.error_type,
                    last_result.error.error_message,
                    last_result.error.traceback,
                )
                raise FinishedWithError(
                    unique_id=unique_id,
                    error=last_result.error.error_type,
                    message=last_result.error.error_message,
                    traceback=last_result.error.traceback,
                )

            # NOTE: this edge case should not happen
            raise UnexpectedNoMoreRetryAttemptsError(
                unique_id=unique_id,
                retry_count=retry_count,
                remaining_attempts=remaining_attempts,
                last_result=last_result,
            )

    async def _start_job_if_missing(
        self,
        name: RemoteHandlerName,
        unique_id: JobUniqueId,
        params: StartParams,
        timeout: timedelta,  # noqa: ASYNC109
    ) -> None:
        # if job is missing on server side start it
        if await self._rpc_interface.get_status(unique_id) == JobStatus.NOT_FOUND:
            try:
                await self._rpc_interface.start(
                    name, unique_id, timeout=timeout, **params
                )
                await self._store_interface.update_entry_expiry(
                    unique_id, expire=timeout
                )
            except AlreadyStartedError:
                _logger.info(
                    "unique_id='%s', was already running, did not start", unique_id
                )

    async def _format_remaining_attempts(
        self, unique_id: JobUniqueId, retry_count: NonNegativeInt
    ) -> str:
        """returns a string in the follwoing format `[{remaining}/{total}]`"""
        schedule_data = await self._store_interface.get(unique_id)
        attempt = (
            "unknown"
            if schedule_data is None
            else retry_count - schedule_data.remaining_attempts
        )
        return f"[{attempt}/{retry_count}]"

    async def _poll_for_result(
        self,
        *,
        name: RemoteHandlerName,
        correlation_id: CorrelationID,
        unique_id: JobUniqueId,
        retry_count: NonNegativeInt,
        timeout: timedelta,  # noqa: ASYNC109
        params: StartParams,
    ) -> ResultModel:
        not_completed: bool = True

        last_result: ResultModel | None = None
        while not_completed:
            await self._track_job_if_not_tracked(
                name, unique_id, correlation_id, params, retry_count, timeout
            )

            await self._decrease_remaining_attempts_or_raise(
                unique_id, retry_count, last_result
            )

            await self._start_job_if_missing(name, unique_id, params, timeout)

            # check if job is present on server side, if not wait a bit before retrying
            status = await self._rpc_interface.get_status(unique_id)
            if status == JobStatus.NOT_FOUND:
                _logger.debug(
                    "'%s' could not be found on remote, waiting %s before retrying",
                    unique_id,
                    _SLEEP_BEFORE_RETRY,
                )
                await asyncio.sleep(_SLEEP_BEFORE_RETRY.total_seconds())
                continue  # tries again if there any attempts left

            # wait until it's done
            sleep_for = _STATUS_POLL_RATE.total_seconds()
            while status == JobStatus.RUNNING:
                await asyncio.sleep(sleep_for)
                status = await self._rpc_interface.get_status(unique_id)

            if status == JobStatus.NOT_FOUND:
                raise UnexpectedStatusError(status=status, unique_id=unique_id)

            if status == JobStatus.FINISHED:
                result: ResultModel = await self._rpc_interface.get_result(unique_id)
                last_result = result

                if result.error is not None:
                    _logger.debug(
                        "'%s' '%s' ended with error='%s'", name, unique_id, result.error
                    )
                    await asyncio.sleep(_SLEEP_BEFORE_RETRY.total_seconds())
                    continue  # tries again if there any attempts left

                break  # successful resul found
        assert result is not None  # nosec
        return result

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    async def ensure_result(
        self,
        name: RemoteHandlerName,
        *,
        expected_type: type[ResultType],
        timeout: timedelta,  # noqa: ASYNC109
        is_unique: bool = False,
        retry_count: Annotated[NonNegativeInt, Field(gt=0)] = 3,
        **params: Any,
    ) -> ResultType:

        correlation_id = _get_correlation_id(is_unique=is_unique)
        unique_id = UniqueIdModel(
            name=name, correlation_id=correlation_id, params=params
        ).unique_id

        try:
            result = await asyncio.wait_for(
                self._poll_for_result(
                    name=name,
                    correlation_id=correlation_id,
                    unique_id=unique_id,
                    retry_count=retry_count,
                    timeout=timeout,
                    params=params,
                ),
                timeout=timeout.total_seconds(),
            )

            result_type = type(result.data)
            if result_type is not expected_type:
                raise UnexpectedResultTypeError(
                    result=result, result_type=result_type, expected_type=expected_type
                )

            assert type(result.data) is expected_type  # nosec
            return result.data
        except TimeoutError as e:
            remaining_attempts = await self._format_remaining_attempts(
                unique_id, retry_count
            )
            raise TimedOutError(
                unique_id=unique_id,
                timeout=timeout,
                remaining_attempts=remaining_attempts,
            ) from e
        finally:
            # when completed remove the task form memory both on the server and the client
            # NOTE: unsure if these should be caught and ignored. In the case we decide to
            # catch them there should be some automatic cleanup in case they are forgotten

            # remove from remote executor
            await self._rpc_interface.remove(unique_id)
            # remove distributed storage (redis)
            await self._store_interface.remove(unique_id)
