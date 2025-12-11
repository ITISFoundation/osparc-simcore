# TODO: this module has to disappear
import functools
from dataclasses import dataclass

from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobId,
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
from servicelib.celery.models import OwnerMetadata
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.async_jobs import async_jobs

from ..exceptions.service_errors_utils import service_exception_mapper
from ..exceptions.task_errors import (
    TaskCancelledError,
    TaskError,
    TaskResultMissingError,
    TaskSchedulerError,
)

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
        self, *, job_id: AsyncJobId, owner_metadata: OwnerMetadata
    ) -> None:
        return await async_jobs.cancel(
            self._rabbitmq_rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            job_id=job_id,
            owner_metadata=owner_metadata,
        )

    @_exception_mapper(
        rpc_exception_map={
            JobSchedulerError: TaskSchedulerError,
        }
    )
    async def status(
        self, *, job_id: AsyncJobId, owner_metadata: OwnerMetadata
    ) -> AsyncJobStatus:
        return await async_jobs.status(
            self._rabbitmq_rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            job_id=job_id,
            owner_metadata=owner_metadata,
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
        self, *, job_id: AsyncJobId, owner_metadata: OwnerMetadata
    ) -> AsyncJobResult:
        return await async_jobs.result(
            self._rabbitmq_rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            job_id=job_id,
            owner_metadata=owner_metadata,
        )

    @_exception_mapper(
        rpc_exception_map={
            JobSchedulerError: TaskSchedulerError,
        }
    )
    async def list_jobs(self, *, owner_metadata: OwnerMetadata) -> list[AsyncJobGet]:
        return await async_jobs.list_jobs(
            self._rabbitmq_rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            owner_metadata=owner_metadata,
        )
