from typing import Any

from servicelib.long_running_tasks import lrt_api
from servicelib.long_running_tasks.models import LRTNamespace, ProgressCallback, TaskId
from servicelib.rabbitmq import RabbitMQRPCClient
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)


async def get_lrt_result(
    rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    task_id: TaskId,
    status_poll_interval: float,
    task_timeout: float,
    progress_callback: ProgressCallback | None = None,
) -> Any:
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(task_timeout),
        wait=wait_fixed(status_poll_interval),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            status = await lrt_api.get_task_status(
                rpc_client,
                lrt_namespace=lrt_namespace,
                task_context={},
                task_id=task_id,
            )

            if progress_callback:
                await progress_callback(status.task_progress.message, status.task_progress.percent, task_id)
            assert status.done is True

    return await lrt_api.get_task_result(
        rpc_client,
        lrt_namespace=lrt_namespace,
        task_context={},
        task_id=task_id,
    )
