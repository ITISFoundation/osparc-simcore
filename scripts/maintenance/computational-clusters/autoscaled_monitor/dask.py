import contextlib
from collections.abc import AsyncGenerator, Awaitable, Coroutine
from typing import Any, Final

import distributed
import rich
from mypy_boto3_ec2.service_resource import Instance
from pydantic import AnyUrl

from .constants import SSH_USER_NAME, TASK_CANCEL_EVENT_NAME_TEMPLATE
from .ec2 import get_bastion_instance_from_remote_instance
from .models import AppState, ComputationalCluster, TaskId, TaskState
from .ssh import ssh_tunnel

_SCHEDULER_PORT: Final[int] = 8786


def _wrap_dask_async_call(called_fct) -> Awaitable[Any]:
    assert isinstance(called_fct, Coroutine)
    return called_fct


@contextlib.asynccontextmanager
async def dask_client(
    state: AppState, instance: Instance
) -> AsyncGenerator[distributed.Client, None]:
    security = distributed.Security()
    assert state.deploy_config
    dask_certificates = state.deploy_config / "assets" / "dask-certificates"
    if dask_certificates.exists():
        security = distributed.Security(
            tls_ca_file=f"{dask_certificates / 'dask-cert.pem'}",
            tls_client_cert=f"{dask_certificates / 'dask-cert.pem'}",
            tls_client_key=f"{dask_certificates / 'dask-key.pem'}",
            require_encryption=True,
        )

    try:
        async with contextlib.AsyncExitStack() as stack:
            if instance.public_ip_address is not None:
                url = AnyUrl(f"tls://{instance.public_ip_address}:{_SCHEDULER_PORT}")
            else:
                bastion_instance = await get_bastion_instance_from_remote_instance(
                    state, instance
                )
                assert state.ssh_key_path  # nosec
                assert state.environment  # nosec
                tunnel = stack.enter_context(
                    ssh_tunnel(
                        ssh_host=bastion_instance.public_dns_name,
                        username=SSH_USER_NAME,
                        private_key_path=state.ssh_key_path,
                        remote_bind_host=instance.private_ip_address,
                        remote_bind_port=_SCHEDULER_PORT,
                    )
                )
                assert tunnel  # nosec
                host, port = tunnel.local_bind_address
                url = AnyUrl(f"tls://{host}:{port}")
            client = await stack.enter_async_context(
                distributed.Client(
                    f"{url}", security=security, timeout="5", asynchronous=True
                )
            )
            yield client

    finally:
        pass


async def remove_job_from_scheduler(
    state: AppState,
    cluster: ComputationalCluster,
    task_id: TaskId,
) -> None:
    async with dask_client(state, cluster.primary.ec2_instance) as client:
        await _wrap_dask_async_call(client.unpublish_dataset(task_id))
        rich.print(f"unpublished {task_id} from scheduler")


async def trigger_job_cancellation_in_scheduler(
    state: AppState,
    cluster: ComputationalCluster,
    task_id: TaskId,
) -> None:
    async with dask_client(state, cluster.primary.ec2_instance) as client:
        task_future = distributed.Future(task_id, client=client)
        cancel_event = distributed.Event(
            name=TASK_CANCEL_EVENT_NAME_TEMPLATE.format(task_future.key),
            client=client,
        )
        await _wrap_dask_async_call(cancel_event.set())
        await _wrap_dask_async_call(task_future.cancel())
        rich.print(f"cancelled {task_id} in scheduler/workers")


async def _list_all_tasks(
    client: distributed.Client,
) -> dict[TaskState, list[TaskId]]:
    def _list_tasks(
        dask_scheduler: distributed.Scheduler,
    ) -> dict[TaskId, TaskState]:
        # NOTE: this is ok and needed: this runs on the dask scheduler, so don't remove this import

        task_state_to_tasks = {}
        for task in dask_scheduler.tasks.values():
            if task.state in task_state_to_tasks:
                task_state_to_tasks[task.state].append(task.key)
            else:
                task_state_to_tasks[task.state] = [task.key]

        return dict(task_state_to_tasks)

    list_of_tasks: dict[TaskState, list[TaskId]] = {}
    try:
        list_of_tasks = await client.run_on_scheduler(_list_tasks)  # type: ignore
    except TypeError:
        rich.print(
            f"ERROR while recoverring unrunnable tasks using {dask_client=}. Defaulting to empty list of tasks!!"
        )
    return list_of_tasks


async def get_scheduler_details(state: AppState, instance: Instance):
    scheduler_info = {}
    datasets_on_cluster = ()
    processing_jobs = {}
    all_tasks = {}
    with contextlib.suppress(TimeoutError, OSError):
        async with dask_client(state, instance) as client:
            scheduler_info = client.scheduler_info()
            datasets_on_cluster = await _wrap_dask_async_call(client.list_datasets())
            processing_jobs = await _wrap_dask_async_call(client.processing())
            all_tasks = await _list_all_tasks(client)

    return scheduler_info, datasets_on_cluster, processing_jobs, all_tasks


def get_worker_metrics(scheduler_info: dict[str, Any]) -> dict[str, Any]:
    worker_metrics = {}
    for worker_name, worker_data in scheduler_info.get("workers", {}).items():
        worker_metrics[worker_name] = {
            "resources": worker_data["resources"],
            "tasks": worker_data["metrics"].get("task_counts", {}),
        }
    return worker_metrics
