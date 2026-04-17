import functools
from dataclasses import dataclass

from celery_library.async_jobs import cancel_job, get_job_result, get_job_status, list_jobs
from models_library.api_schemas_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobId,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.api_schemas_async_jobs.exceptions import (
    JobAbortedError,
    JobError,
    JobNotDoneError,
    JobSchedulerError,
)
from servicelib.celery.task_manager import TaskManager

from ..exceptions.service_errors_utils import service_exception_mapper
from ..exceptions.task_errors import (
    TaskCancelledError,
    TaskError,
    TaskResultMissingError,
    TaskSchedulerError,
)

_exception_mapper = functools.partial(service_exception_mapper, service_name="Async jobs")


@dataclass
class AsyncJobClient:
    _task_manager: TaskManager

    @_exception_mapper(
        rpc_exception_map={
            JobSchedulerError: TaskSchedulerError,
        }
    )
    async def cancel(self, *, job_id: AsyncJobId) -> None:
        return await cancel_job(
            self._task_manager,
            job_id=job_id,
        )

    @_exception_mapper(
        rpc_exception_map={
            JobSchedulerError: TaskSchedulerError,
        }
    )
    async def status(self, *, job_id: AsyncJobId) -> AsyncJobStatus:
        return await get_job_status(
            self._task_manager,
            job_id=job_id,
        )

    @_exception_mapper(
        rpc_exception_map={
            JobSchedulerError: TaskSchedulerError,
            JobNotDoneError: TaskResultMissingError,
            JobAbortedError: TaskCancelledError,
            JobError: TaskError,
        }
    )
    async def result(self, *, job_id: AsyncJobId) -> AsyncJobResult:
        return await get_job_result(
            self._task_manager,
            job_id=job_id,
        )

    @_exception_mapper(
        rpc_exception_map={
            JobSchedulerError: TaskSchedulerError,
        }
    )
    async def list_jobs(
        self,
        *,
        owner: str,
        user_id: int | None = None,
        product_name: str | None = None,
    ) -> list[AsyncJobGet]:
        return await list_jobs(
            self._task_manager,
            owner=owner,
            user_id=user_id,
            product_name=product_name,
        )
