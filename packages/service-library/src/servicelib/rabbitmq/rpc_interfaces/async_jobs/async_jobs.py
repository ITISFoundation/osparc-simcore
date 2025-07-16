import datetime
import logging
from asyncio import CancelledError
from collections.abc import AsyncGenerator, Awaitable
from typing import Any, Final

from attr import dataclass
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobFilter,
    AsyncJobGet,
    AsyncJobId,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.api_schemas_rpc_async_jobs.exceptions import JobMissingError
from models_library.rabbitmq_basic_types import RPCMethodName, RPCNamespace
from pydantic import NonNegativeInt, TypeAdapter
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

from ....rabbitmq import RemoteMethodNotRegisteredError
from ... import RabbitMQRPCClient

_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 30
_DEFAULT_POLL_INTERVAL_S: Final[float] = 0.1

_logger = logging.getLogger(__name__)


async def cancel(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    job_id: AsyncJobId,
    job_filter: AsyncJobFilter,
) -> None:
    await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("cancel"),
        job_id=job_id,
        job_filter=job_filter,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )


async def status(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    job_id: AsyncJobId,
    job_filter: AsyncJobFilter,
) -> AsyncJobStatus:
    _result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("status"),
        job_id=job_id,
        job_filter=job_filter,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(_result, AsyncJobStatus)
    return _result


async def result(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    job_id: AsyncJobId,
    job_filter: AsyncJobFilter,
) -> AsyncJobResult:
    _result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("result"),
        job_id=job_id,
        job_filter=job_filter,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(_result, AsyncJobResult)
    return _result


async def list_jobs(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    filter_: str,
    job_filter: AsyncJobFilter,
) -> list[AsyncJobGet]:
    _result: list[AsyncJobGet] = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("list_jobs"),
        filter_=filter_,
        job_filter=job_filter,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    return _result


async def submit(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    method_name: str,
    job_filter: AsyncJobFilter,
    **kwargs,
) -> AsyncJobGet:
    _result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python(method_name),
        job_filter=job_filter,
        **kwargs,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(_result, AsyncJobGet)  # nosec
    return _result


_DEFAULT_RPC_RETRY_POLICY: dict[str, Any] = {
    "retry": retry_if_exception_type((RemoteMethodNotRegisteredError,)),
    "wait": wait_random_exponential(max=20),
    "stop": stop_after_attempt(30),
    "reraise": True,
    "before_sleep": before_sleep_log(_logger, logging.WARNING),
}


@retry(**_DEFAULT_RPC_RETRY_POLICY)
async def _wait_for_completion(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    method_name: RPCMethodName,
    job_id: AsyncJobId,
    job_filter: AsyncJobFilter,
    client_timeout: datetime.timedelta,
) -> AsyncGenerator[AsyncJobStatus, None]:
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_delay(client_timeout.total_seconds()),
            reraise=True,
            retry=retry_if_exception_type((TryAgain, JobMissingError)),
            before_sleep=before_sleep_log(_logger, logging.DEBUG),
            wait=wait_fixed(_DEFAULT_POLL_INTERVAL_S),
        ):
            with attempt:
                job_status = await status(
                    rabbitmq_rpc_client,
                    rpc_namespace=rpc_namespace,
                    job_id=job_id,
                    job_filter=job_filter,
                )
                yield job_status
                if not job_status.done:
                    msg = f"{job_status.job_id=}: '{job_status.progress=}'"
                    raise TryAgain(msg)  # noqa: TRY301

    except TryAgain as exc:
        # this is a timeout
        msg = f"Async job {job_id=}, calling to '{method_name}' timed-out after {client_timeout}"
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
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    method_name: str,
    job_id: AsyncJobId,
    job_filter: AsyncJobFilter,
    client_timeout: datetime.timedelta,
) -> AsyncGenerator[AsyncJobComposedResult, None]:
    """when a job is already submitted this will wait for its completion
    and return the composed result"""
    try:
        job_status = None
        async for job_status in _wait_for_completion(
            rabbitmq_rpc_client,
            rpc_namespace=rpc_namespace,
            method_name=method_name,
            job_id=job_id,
            job_filter=job_filter,
            client_timeout=client_timeout,
        ):
            assert job_status is not None  # nosec
            yield AsyncJobComposedResult(job_status)

        # return the result
        if job_status:
            yield AsyncJobComposedResult(
                job_status,
                result(
                    rabbitmq_rpc_client,
                    rpc_namespace=rpc_namespace,
                    job_id=job_id,
                    job_filter=job_filter,
                ),
            )
    except (TimeoutError, CancelledError) as error:
        try:
            await cancel(
                rabbitmq_rpc_client,
                rpc_namespace=rpc_namespace,
                job_id=job_id,
                job_filter=job_filter,
            )
        except Exception as exc:
            raise exc from error  # NOSONAR
        raise


async def submit_and_wait(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    method_name: str,
    job_filter: AsyncJobFilter,
    client_timeout: datetime.timedelta,
    **kwargs,
) -> AsyncGenerator[AsyncJobComposedResult, None]:
    async_job_rpc_get = None
    try:
        async_job_rpc_get = await submit(
            rabbitmq_rpc_client,
            rpc_namespace=rpc_namespace,
            method_name=method_name,
            job_filter=job_filter,
            **kwargs,
        )
    except (TimeoutError, CancelledError) as error:
        if async_job_rpc_get is not None:
            try:
                await cancel(
                    rabbitmq_rpc_client,
                    rpc_namespace=rpc_namespace,
                    job_id=async_job_rpc_get.job_id,
                    job_filter=job_filter,
                )
            except Exception as exc:
                raise exc from error
        raise

    async for wait_and_ in wait_and_get_result(
        rabbitmq_rpc_client,
        rpc_namespace=rpc_namespace,
        method_name=method_name,
        job_id=async_job_rpc_get.job_id,
        job_filter=job_filter,
        client_timeout=client_timeout,
    ):
        yield wait_and_
