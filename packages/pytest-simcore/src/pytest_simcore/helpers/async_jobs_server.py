from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobId,
    AsyncJobNameData,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.progress_bar import ProgressReport
from models_library.rabbitmq_basic_types import RPCNamespace
from pydantic import validate_call
from pytest_mock import MockType
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient


class AsyncJobSideEffects:

    @validate_call(config={"arbitrary_types_allowed": True})
    async def cancel(
        self,
        rabbitmq_rpc_client: RabbitMQRPCClient | MockType,
        *,
        rpc_namespace: RPCNamespace,
        job_id: AsyncJobId,
        job_id_data: AsyncJobNameData,
    ) -> None:
        pass

    @validate_call(config={"arbitrary_types_allowed": True})
    async def status(
        self,
        rabbitmq_rpc_client: RabbitMQRPCClient | MockType,
        *,
        rpc_namespace: RPCNamespace,
        job_id: AsyncJobId,
        job_id_data: AsyncJobNameData,
    ) -> AsyncJobStatus:
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
        job_id_data: AsyncJobNameData,
    ) -> AsyncJobResult:
        return AsyncJobResult(result="Success")

    @validate_call(config={"arbitrary_types_allowed": True})
    async def list_jobs(
        self,
        rabbitmq_rpc_client: RabbitMQRPCClient | MockType,
        *,
        rpc_namespace: RPCNamespace,
        job_id_data: AsyncJobNameData,
        filter_: str = "",
    ) -> list[AsyncJobGet]:
        return [
            AsyncJobGet(
                job_id=AsyncJobId("123e4567-e89b-12d3-a456-426614174000"),
                job_name="Example Job",
            )
        ]
