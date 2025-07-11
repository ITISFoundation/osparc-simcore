# pylint: disable=unused-argument

from dataclasses import dataclass

from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobFilter,
    AsyncJobGet,
    AsyncJobId,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.api_schemas_rpc_async_jobs.exceptions import BaseAsyncjobRpcError
from models_library.progress_bar import ProgressReport
from models_library.rabbitmq_basic_types import RPCNamespace
from pydantic import validate_call
from pytest_mock import MockType
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient


@dataclass
class AsyncJobSideEffects:
    exception: BaseAsyncjobRpcError | None = None

    @validate_call(config={"arbitrary_types_allowed": True})
    async def cancel(
        self,
        rabbitmq_rpc_client: RabbitMQRPCClient | MockType,
        *,
        rpc_namespace: RPCNamespace,
        job_id: AsyncJobId,
        job_filter: AsyncJobFilter,
    ) -> None:
        if self.exception is not None:
            raise self.exception
        return None

    @validate_call(config={"arbitrary_types_allowed": True})
    async def status(
        self,
        rabbitmq_rpc_client: RabbitMQRPCClient | MockType,
        *,
        rpc_namespace: RPCNamespace,
        job_id: AsyncJobId,
        job_filter: AsyncJobFilter,
    ) -> AsyncJobStatus:
        if self.exception is not None:
            raise self.exception

        return AsyncJobStatus(
            job_id=job_id,
            progress=ProgressReport(
                actual_value=50.0,
                total=100.0,
                attempt=1,
            ),
            done=False,
        )

    @validate_call(config={"arbitrary_types_allowed": True})
    async def result(
        self,
        rabbitmq_rpc_client: RabbitMQRPCClient | MockType,
        *,
        rpc_namespace: RPCNamespace,
        job_id: AsyncJobId,
        job_filter: AsyncJobFilter,
    ) -> AsyncJobResult:
        if self.exception is not None:
            raise self.exception
        return AsyncJobResult(result="Success")

    @validate_call(config={"arbitrary_types_allowed": True})
    async def list_jobs(
        self,
        rabbitmq_rpc_client: RabbitMQRPCClient | MockType,
        *,
        rpc_namespace: RPCNamespace,
        job_filter: AsyncJobFilter,
        filter_: str = "",
    ) -> list[AsyncJobGet]:
        if self.exception is not None:
            raise self.exception
        return [
            AsyncJobGet(
                job_id=AsyncJobId("123e4567-e89b-12d3-a456-426614174000"),
                job_name="Example Job",
            )
        ]
