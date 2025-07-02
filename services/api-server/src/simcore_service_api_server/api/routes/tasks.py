import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
    TaskResult,
    TaskStatus,
)
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobId,
    AsyncJobNameData,
)
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.async_jobs import async_jobs

from ..dependencies.authentication import get_current_user_id
from ..dependencies.rabbitmq import get_rabbitmq_rpc_client
from ..dependencies.services import get_product_name

router = APIRouter()
_logger = logging.getLogger(__name__)


# Helper to build job_id_data from user context (for demo, expects user_id and product_name as query params)
def _get_job_id_data(user_id: UserID, product_name: ProductName) -> AsyncJobNameData:
    return AsyncJobNameData(user_id=user_id, product_name=product_name)


@router.get("", response_model=list[TaskGet])
async def get_async_jobs(
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
    rabbitmq_rpc_client: Annotated[RabbitMQRPCClient, Depends(get_rabbitmq_rpc_client)],
):
    user_async_jobs = await async_jobs.list_jobs(
        rabbitmq_rpc_client=rabbitmq_rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id_data=_get_job_id_data(user_id, product_name),
        filter_="",
    )
    return [
        TaskGet(
            task_id=str(job.job_id),
            task_name=job.job_name,
            status_href=router.url_path_for(
                "get_async_job_status", task_id=str(job.job_id)
            ),
            abort_href=router.url_path_for("cancel_async_job", task_id=str(job.job_id)),
            result_href=router.url_path_for(
                "get_async_job_result", task_id=str(job.job_id)
            ),
        )
        for job in user_async_jobs
    ]


@router.get("/{task_id}", response_model=TaskStatus, name="get_async_job_status")
async def get_async_job_status(
    task_id: AsyncJobId,
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
    rabbitmq_rpc_client: Annotated[RabbitMQRPCClient, Depends(get_rabbitmq_rpc_client)],
):
    async_job_rpc_status = await async_jobs.status(
        rabbitmq_rpc_client=rabbitmq_rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id=task_id,
        job_id_data=_get_job_id_data(user_id, product_name),
    )
    _task_id = str(async_job_rpc_status.job_id)
    return TaskStatus(
        task_progress=TaskProgress(
            task_id=_task_id, percent=async_job_rpc_status.progress.percent_value
        ),
        done=async_job_rpc_status.done,
        started=None,
    )


@router.delete(
    "/{task_id}/cancel", status_code=status.HTTP_204_NO_CONTENT, name="cancel_async_job"
)
async def cancel_async_job(
    task_id: AsyncJobId,
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
    rabbitmq_rpc_client: Annotated[RabbitMQRPCClient, Depends(get_rabbitmq_rpc_client)],
):
    await async_jobs.cancel(
        rabbitmq_rpc_client=rabbitmq_rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id=task_id,
        job_id_data=_get_job_id_data(user_id, product_name),
    )
    return


@router.get("/{task_id}/result", response_model=TaskResult, name="get_async_job_result")
async def get_async_job_result(
    task_id: AsyncJobId,
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
    rabbitmq_rpc_client: Annotated[RabbitMQRPCClient, Depends(get_rabbitmq_rpc_client)],
):
    async_job_rpc_result = await async_jobs.result(
        rabbitmq_rpc_client=rabbitmq_rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id=task_id,
        job_id_data=_get_job_id_data(user_id, product_name),
    )
    return TaskResult(result=async_job_rpc_result.result, error=None)
