import collections
import contextlib
import logging
import re
from collections import defaultdict
from collections.abc import AsyncIterator, Coroutine
from typing import Any, Final, TypeAlias

import dask.typing
import distributed
import distributed.scheduler
from aws_library.ec2 import EC2InstanceData, Resources
from dask_task_models_library.resource_constraints import DaskTaskResources
from distributed.core import Status
from models_library.clusters import InternalClusterAuthentication, TLSAuthentication
from pydantic import AnyUrl, ByteSize, TypeAdapter

from ..core.errors import (
    DaskNoWorkersError,
    DaskSchedulerNotFoundError,
    DaskWorkerNotFoundError,
)
from ..models import AssociatedInstance, DaskTask, DaskTaskId
from ..utils.auto_scaling_core import (
    node_host_name_from_ec2_private_dns,
    node_ip_from_ec2_private_dns,
)

_logger = logging.getLogger(__name__)


async def _wrap_client_async_routine(
    client_coroutine: Coroutine[Any, Any, Any] | Any | None
) -> Any:
    """Dask async behavior does not go well with Pylance as it returns
    a union of types. this wrapper makes both mypy and pylance happy"""
    assert client_coroutine  # nosec
    return await client_coroutine


_DASK_SCHEDULER_CONNECT_TIMEOUT_S: Final[int] = 5


@contextlib.asynccontextmanager
async def _scheduler_client(
    url: AnyUrl, authentication: InternalClusterAuthentication
) -> AsyncIterator[distributed.Client]:
    """
    Raises:
        DaskSchedulerNotFoundError: if the scheduler was not found/cannot be reached
    """
    try:
        security = distributed.Security()
        if isinstance(authentication, TLSAuthentication):
            security = distributed.Security(
                tls_ca_file=f"{authentication.tls_ca_file}",
                tls_client_cert=f"{authentication.tls_client_cert}",
                tls_client_key=f"{authentication.tls_client_key}",
                require_encryption=True,
            )
        async with distributed.Client(
            f"{url}",
            asynchronous=True,
            timeout=f"{_DASK_SCHEDULER_CONNECT_TIMEOUT_S}",
            security=security,
        ) as client:
            yield client
    except OSError as exc:
        raise DaskSchedulerNotFoundError(url=url) from exc


DaskWorkerUrl: TypeAlias = str
DaskWorkerDetails: TypeAlias = dict[str, Any]
DASK_NAME_PATTERN: Final[re.Pattern] = re.compile(
    r"^(?P<host_name>.+)_(?P<private_ip>ip-\d{1,3}-\d{1,3}-\d{1,3}-\d{1,3})[-_].*$"
)


def _dask_worker_from_ec2_instance(
    client: distributed.Client, ec2_instance: EC2InstanceData
) -> tuple[DaskWorkerUrl, DaskWorkerDetails]:
    """
    Raises:
        Ec2InvalidDnsNameError
        DaskNoWorkersError
        DaskWorkerNotFoundError
    """
    node_hostname = node_host_name_from_ec2_private_dns(ec2_instance)
    scheduler_info = client.scheduler_info()
    assert client.scheduler  # nosec
    if "workers" not in scheduler_info or not scheduler_info["workers"]:
        raise DaskNoWorkersError(url=client.scheduler.address)
    workers: dict[DaskWorkerUrl, DaskWorkerDetails] = scheduler_info["workers"]

    _logger.debug("looking for %s in %s", f"{ec2_instance=}", f"{workers=}")

    # dict is of type dask_worker_address: worker_details
    def _find_by_worker_host(
        dask_worker: tuple[DaskWorkerUrl, DaskWorkerDetails]
    ) -> bool:
        _, details = dask_worker
        if match := re.match(DASK_NAME_PATTERN, details["name"]):
            return bool(match.group("private_ip") == node_hostname)
        return False

    filtered_workers = dict(filter(_find_by_worker_host, workers.items()))
    if not filtered_workers:
        raise DaskWorkerNotFoundError(
            worker_host=ec2_instance.aws_private_dns, url=client.scheduler.address
        )
    assert (
        len(filtered_workers) == 1
    ), f"returned workers {filtered_workers}, {node_hostname=}"  # nosec
    return next(iter(filtered_workers.items()))


async def is_worker_connected(
    scheduler_url: AnyUrl,
    authentication: InternalClusterAuthentication,
    worker_ec2_instance: EC2InstanceData,
) -> bool:
    with contextlib.suppress(DaskNoWorkersError, DaskWorkerNotFoundError):
        async with _scheduler_client(scheduler_url, authentication) as client:
            _, worker_details = _dask_worker_from_ec2_instance(
                client, worker_ec2_instance
            )
            return Status(worker_details["status"]) == Status.running
    return False


async def is_worker_retired(
    scheduler_url: AnyUrl,
    authentication: InternalClusterAuthentication,
    worker_ec2_instance: EC2InstanceData,
) -> bool:
    with contextlib.suppress(DaskNoWorkersError, DaskWorkerNotFoundError):
        async with _scheduler_client(scheduler_url, authentication) as client:
            _, worker_details = _dask_worker_from_ec2_instance(
                client, worker_ec2_instance
            )
            return Status(worker_details["status"]) in {
                Status.closed,
                Status.closing,
                Status.closing_gracefully,
            }
    return False


def _dask_key_to_dask_task_id(key: dask.typing.Key) -> DaskTaskId:
    if isinstance(key, bytes):
        return key.decode("utf-8")
    if isinstance(key, tuple):
        return "(" + ", ".join(_dask_key_to_dask_task_id(k) for k in key) + ")"
    return f"{key}"


async def list_unrunnable_tasks(
    scheduler_url: AnyUrl,
    authentication: InternalClusterAuthentication,
) -> list[DaskTask]:
    """
    Raises:
        DaskSchedulerNotFoundError
    """

    def _list_tasks(
        dask_scheduler: distributed.Scheduler,
    ) -> dict[dask.typing.Key, dict[str, float]]:
        # NOTE: task.key can be a byte, str, or a tuple
        return {
            task.key: task.resource_restrictions or {}
            for task in dask_scheduler.unrunnable
        }

    async with _scheduler_client(scheduler_url, authentication) as client:
        list_of_tasks: dict[
            dask.typing.Key, DaskTaskResources
        ] = await _wrap_client_async_routine(client.run_on_scheduler(_list_tasks))
        _logger.debug("found unrunnable tasks: %s", list_of_tasks)
        return [
            DaskTask(
                task_id=_dask_key_to_dask_task_id(task_id),
                required_resources=task_resources,
            )
            for task_id, task_resources in list_of_tasks.items()
        ]


async def list_processing_tasks_per_worker(
    scheduler_url: AnyUrl,
    authentication: InternalClusterAuthentication,
) -> dict[DaskWorkerUrl, list[DaskTask]]:
    """
    Raises:
        DaskSchedulerNotFoundError
    """

    def _list_processing_tasks(
        dask_scheduler: distributed.Scheduler,
    ) -> dict[str, list[tuple[dask.typing.Key, DaskTaskResources]]]:
        worker_to_processing_tasks = defaultdict(list)
        for task_key, task_state in dask_scheduler.tasks.items():
            if task_state.processing_on:
                worker_to_processing_tasks[task_state.processing_on.address].append(
                    (task_key, task_state.resource_restrictions or {})
                )
        return worker_to_processing_tasks

    async with _scheduler_client(scheduler_url, authentication) as client:
        worker_to_tasks: dict[
            str, list[tuple[dask.typing.Key, DaskTaskResources]]
        ] = await _wrap_client_async_routine(
            client.run_on_scheduler(_list_processing_tasks)
        )
        _logger.debug("found processing tasks: %s", worker_to_tasks)
        tasks_per_worker = defaultdict(list)
        for worker, tasks in worker_to_tasks.items():
            for task_id, required_resources in tasks:
                tasks_per_worker[worker].append(
                    DaskTask(
                        task_id=_dask_key_to_dask_task_id(task_id),
                        required_resources=required_resources,
                    )
                )
        return tasks_per_worker


async def get_worker_still_has_results_in_memory(
    scheduler_url: AnyUrl,
    authentication: InternalClusterAuthentication,
    ec2_instance: EC2InstanceData,
) -> int:
    """
    Raises:
        DaskSchedulerNotFoundError
        Ec2InvalidDnsNameError
        DaskWorkerNotFoundError
        DaskNoWorkersError
    """
    async with _scheduler_client(scheduler_url, authentication) as client:
        _, worker_details = _dask_worker_from_ec2_instance(client, ec2_instance)

        worker_metrics: dict[str, Any] = worker_details["metrics"]
        return 1 if worker_metrics.get("task_counts") else 0


async def get_worker_used_resources(
    scheduler_url: AnyUrl,
    authentication: InternalClusterAuthentication,
    ec2_instance: EC2InstanceData,
) -> Resources:
    """
    Raises:
        DaskSchedulerNotFoundError
        Ec2InvalidDnsNameError
        DaskWorkerNotFoundError
        DaskNoWorkersError
    """

    def _list_processing_tasks_on_worker(
        dask_scheduler: distributed.Scheduler, *, worker_url: str
    ) -> list[tuple[dask.typing.Key, DaskTaskResources]]:
        processing_tasks = []
        for task_key, task_state in dask_scheduler.tasks.items():
            if task_state.processing_on and (
                task_state.processing_on.address == worker_url
            ):
                processing_tasks.append(
                    (task_key, task_state.resource_restrictions or {})
                )
        return processing_tasks

    async with _scheduler_client(scheduler_url, authentication) as client:
        worker_url, _ = _dask_worker_from_ec2_instance(client, ec2_instance)

        _logger.debug("looking for processing tasksfor %s", f"{worker_url=}")

        # now get the used resources
        worker_processing_tasks: list[
            tuple[dask.typing.Key, DaskTaskResources]
        ] = await _wrap_client_async_routine(
            client.run_on_scheduler(
                _list_processing_tasks_on_worker, worker_url=worker_url
            ),
        )

        total_resources_used: collections.Counter[str] = collections.Counter()
        for _, task_resources in worker_processing_tasks:
            total_resources_used.update(task_resources)

        _logger.debug("found %s for %s", f"{total_resources_used=}", f"{worker_url=}")
        return Resources(
            cpus=total_resources_used.get("CPU", 0),
            ram=TypeAdapter(ByteSize).validate_python(
                total_resources_used.get("RAM", 0)
            ),
        )


async def compute_cluster_total_resources(
    scheduler_url: AnyUrl,
    authentication: InternalClusterAuthentication,
    instances: list[AssociatedInstance],
) -> Resources:
    if not instances:
        return Resources.create_as_empty()
    async with _scheduler_client(scheduler_url, authentication) as client:
        instance_hosts = (
            node_ip_from_ec2_private_dns(i.ec2_instance) for i in instances
        )
        scheduler_info = client.scheduler_info()
        if "workers" not in scheduler_info or not scheduler_info["workers"]:
            raise DaskNoWorkersError(url=scheduler_url)
        workers: dict[str, Any] = scheduler_info["workers"]
        for worker_details in workers.values():
            if worker_details["host"] not in instance_hosts:
                continue

        return Resources.create_as_empty()


async def try_retire_nodes(
    scheduler_url: AnyUrl, authentication: InternalClusterAuthentication
) -> None:
    async with _scheduler_client(scheduler_url, authentication) as client:
        await _wrap_client_async_routine(
            client.retire_workers(close_workers=False, remove=False)
        )
