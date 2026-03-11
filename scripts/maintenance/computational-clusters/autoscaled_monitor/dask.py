import contextlib
from collections.abc import AsyncGenerator, Awaitable, Coroutine
from typing import Any, Final

import asyncssh
import distributed
import rich
from aiocache import SimpleMemoryCache
from distributed.objects import SchedulerInfo
from mypy_boto3_ec2.service_resource import Instance
from pydantic import AnyUrl

from .constants import SSH_USER_NAME, TASK_CANCEL_EVENT_NAME_TEMPLATE
from .ec2 import get_bastion_instance_from_remote_instance
from .models import AppState, ComputationalCluster, TaskId, TaskState
from .ssh import ssh_tunnel

_SCHEDULER_PORT: Final[int] = 8786
_SCHEDULER_CACHE_TTL: Final[int] = 30  # seconds

_scheduler_task_cache: Final = SimpleMemoryCache(ttl=_SCHEDULER_CACHE_TTL)


def _wrap_dask_async_call(called_fct) -> Awaitable[Any]:
    assert isinstance(called_fct, Coroutine)
    return called_fct


@contextlib.asynccontextmanager
async def dask_client(
    state: AppState,
    instance: Instance,
    bastion_conn: asyncssh.SSHClientConnection | None,
) -> AsyncGenerator[distributed.Client]:
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
                if bastion_conn is None:
                    bastion_instance = await get_bastion_instance_from_remote_instance(state, instance)
                    ssh_host = bastion_instance.public_dns_name
                else:
                    ssh_host = instance.private_ip_address
                assert state.ssh_key_path  # nosec
                assert state.environment  # nosec
                host, port = await stack.enter_async_context(
                    ssh_tunnel(
                        ssh_host=ssh_host,
                        username=SSH_USER_NAME,
                        private_key_path=state.ssh_key_path,
                        remote_bind_host=instance.private_ip_address,
                        remote_bind_port=_SCHEDULER_PORT,
                        bastion_conn=bastion_conn,
                    )
                )
                url = AnyUrl(f"tls://{host}:{port}")
            client = await stack.enter_async_context(
                distributed.Client(f"{url}", security=security, timeout="5", asynchronous=True)
            )
            yield client

    finally:
        pass


async def remove_job_from_scheduler(
    state: AppState,
    cluster: ComputationalCluster,
    task_id: TaskId,
    bastion_conn: asyncssh.SSHClientConnection | None,
) -> None:
    async with dask_client(state, cluster.primary.ec2_instance, bastion_conn) as client:
        await _wrap_dask_async_call(client.unpublish_dataset(task_id))
        rich.print(f"unpublished {task_id} from scheduler")


async def trigger_job_cancellation_in_scheduler(
    state: AppState,
    cluster: ComputationalCluster,
    task_id: TaskId,
    bastion_conn: asyncssh.SSHClientConnection | None,
) -> None:
    async with dask_client(state, cluster.primary.ec2_instance, bastion_conn) as client:
        task_future = distributed.Future(task_id, client=client)
        cancel_event = distributed.Event(
            name=TASK_CANCEL_EVENT_NAME_TEMPLATE.format(task_future.key),
            client=client,
        )
        await _wrap_dask_async_call(cancel_event.set())
        await _wrap_dask_async_call(task_future.cancel())
        rich.print(f"cancelled {task_id} in scheduler/workers")


async def _get_cached_scheduler_task_data(client: distributed.Client, instance_id: str) -> dict[str, Any]:  # noqa: C901
    """Single cached call to the scheduler that returns all task data at once."""
    cached_data: dict[str, Any] | None = await _scheduler_task_cache.get(instance_id)
    if cached_data is not None:
        return cached_data

    def _collect_all_task_data(
        dask_scheduler: distributed.Scheduler,
    ) -> dict[str, Any]:
        # NOTE: this runs on the dask scheduler process — must be a local function so
        # cloudpickle serialises it by value (bytecode) rather than by module reference.
        tasks_by_state: dict[str, list[str]] = {}
        task_resources: dict[str, dict[str, Any]] = {}
        for task in dask_scheduler.tasks.values():
            tasks_by_state.setdefault(str(task.state), []).append(str(task.key))
            if task.resource_restrictions:
                task_resources[str(task.key)] = dict(task.resource_restrictions)
        # Collect per-task worker-level state.
        # The scheduler-side WorkerState tracks executing and long_running,
        # but NOT constrained/ready/waiting (those are worker-internal).
        # For tasks in processing but not executing/long_running, we infer
        # constrained vs queued from whether they have resource_restrictions.
        task_worker_states: dict[str, str] = {}
        for worker in dask_scheduler.workers.values():
            known_keys: set[str] = set()
            for task in getattr(worker, "executing", set()):
                key = str(task.key)
                task_worker_states[key] = "executing"
                known_keys.add(key)
            for task in getattr(worker, "long_running", set()):
                key = str(task.key)
                task_worker_states[key] = "long-running"
                known_keys.add(key)
            for task in getattr(worker, "processing", {}):
                key = str(task.key)
                if key not in known_keys:
                    if task.resource_restrictions:
                        task_worker_states[key] = "constrained"
                    else:
                        task_worker_states[key] = "queued"
        return {
            "tasks_by_state": tasks_by_state,
            "task_resources": task_resources,
            "task_worker_states": task_worker_states,
        }

    try:
        data: dict[str, Any] = await client.run_on_scheduler(_collect_all_task_data)  # type: ignore
    except Exception as e:  # pylint: disable=broad-exception-caught
        rich.print(
            f"Unexpected error fetching task data from scheduler: {e} "
            f"when communicating with {client.scheduler}. Defaulting to empty."
        )
        data = {"tasks_by_state": {}, "task_resources": {}, "task_worker_states": {}}
    await _scheduler_task_cache.set(instance_id, data)
    return data


async def get_scheduler_details(
    state: AppState,
    instance: Instance,
    bastion_conn: asyncssh.SSHClientConnection | None,
):
    scheduler_info = {}
    datasets_on_cluster = ()
    processing_jobs = {}
    all_tasks: dict[TaskState, list[TaskId]] = {}
    task_resources: dict[TaskId, dict[str, Any]] = {}
    task_worker_states: dict[TaskId, str] = {}
    try:
        async with dask_client(state, instance, bastion_conn) as client:
            assert client.scheduler  # nosec
            # NOTE: client.scheduler_info() is cached and limited to 5 workers for async clients.
            # Use the direct RPC call instead, which returns all workers live.
            scheduler_info = SchedulerInfo(await client.scheduler.identity(n_workers=-1))  # type: ignore
            datasets_on_cluster = await _wrap_dask_async_call(client.list_datasets())
            processing_jobs = await _wrap_dask_async_call(client.processing())
            task_data = await _get_cached_scheduler_task_data(client, instance.id)
            all_tasks = task_data["tasks_by_state"]
            task_resources = task_data["task_resources"]
            task_worker_states = task_data["task_worker_states"]
    except (TimeoutError, OSError, TypeError):
        rich.print("ERROR while recoverring scheduler details !! no scheduler info found!!")

    return scheduler_info, datasets_on_cluster, processing_jobs, all_tasks, task_resources, task_worker_states


def get_worker_metrics(scheduler_info: dict[str, Any]) -> dict[str, Any]:
    worker_metrics = {}
    for worker_name, worker_data in scheduler_info.get("workers", {}).items():
        worker_metrics[worker_name] = {
            "resources": worker_data["resources"],
            "tasks": worker_data["metrics"].get("task_counts", {}),
        }
    return worker_metrics
