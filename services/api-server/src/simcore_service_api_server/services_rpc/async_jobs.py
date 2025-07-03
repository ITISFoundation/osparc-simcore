import functools
from dataclasses import dataclass

from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobId,
    AsyncJobNameData,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.api_schemas_rpc_async_jobs.exceptions import (
    JobAbortedError,
    JobError,
    JobNotDoneError,
    JobSchedulerError,
)
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.async_jobs import async_jobs
from simcore_service_api_server.exceptions.task_errors import (
    TaskCancelledError,
    TaskError,
    TaskResultMissingError,
    TaskSchedulerError,
)

from ..exceptions.service_errors_utils import service_exception_mapper

_exception_mapper = functools.partial(
    service_exception_mapper, service_name="Async jobs"
)


@dataclass
class AsyncJobClient:
    _rabbitmq_rpc_client: RabbitMQRPCClient

    @_exception_mapper(
        rpc_exception_map={
            JobSchedulerError: TaskSchedulerError,
        }
    )
    async def cancel(
        self, *, job_id: AsyncJobId, job_id_data: AsyncJobNameData
    ) -> None:
        return await async_jobs.cancel(
            self._rabbitmq_rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            job_id=job_id,
            job_id_data=job_id_data,
        )

    @_exception_mapper(
        rpc_exception_map={
            JobSchedulerError: TaskSchedulerError,
        }
    )
    async def status(
        self, *, job_id: AsyncJobId, job_id_data: AsyncJobNameData
    ) -> AsyncJobStatus:
        return await async_jobs.status(
            self._rabbitmq_rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            job_id=job_id,
            job_id_data=job_id_data,
        )

    @_exception_mapper(
        rpc_exception_map={
            JobSchedulerError: TaskSchedulerError,
            JobNotDoneError: TaskResultMissingError,
            JobAbortedError: TaskCancelledError,
            JobError: TaskError,
        }
    )
    async def result(
        self, *, job_id: AsyncJobId, job_id_data: AsyncJobNameData
    ) -> AsyncJobResult:
        return await async_jobs.result(
            self._rabbitmq_rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            job_id=job_id,
            job_id_data=job_id_data,
        )

    @_exception_mapper(
        rpc_exception_map={
            JobSchedulerError: TaskSchedulerError,
        }
    )
    async def list_jobs(
        self, *, filter_: str, job_id_data: AsyncJobNameData
    ) -> list[AsyncJobGet]:
        return await async_jobs.list_jobs(
            self._rabbitmq_rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            filter_=filter_,
            job_id_data=job_id_data,
        )
