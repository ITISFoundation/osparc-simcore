import contextlib
import logging
import re
from collections import defaultdict
from collections.abc import AsyncIterator, Coroutine
from typing import Any, Final, TypeAlias

import distributed
from aws_library.ec2.models import EC2InstanceData, Resources
from dask_task_models_library.resource_constraints import DaskTaskResources
from pydantic import AnyUrl, ByteSize, parse_obj_as

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
async def _scheduler_client(url: AnyUrl) -> AsyncIterator[distributed.Client]:
    """
    Raises:
        DaskSchedulerNotFoundError: if the scheduler was not found/cannot be reached
    """
    try:
        async with distributed.Client(
            url, asynchronous=True, timeout=f"{_DASK_SCHEDULER_CONNECT_TIMEOUT_S}"
        ) as client:
            yield client
    except OSError as exc:
        raise DaskSchedulerNotFoundError(url=url) from exc


DaskWorkerUrl: TypeAlias = str
DaskWorkerDetails: TypeAlias = dict[str, Any]
DASK_NAME_PATTERN: Final[re.Pattern] = re.compile(
    r"^.+_(?P<private_ip>ip-\d+-\d+-\d+-\d+).+$"
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
    scheduler_url: AnyUrl, worker_ec2_instance: EC2InstanceData
) -> bool:
    with contextlib.suppress(DaskNoWorkersError, DaskWorkerNotFoundError):
        async with _scheduler_client(scheduler_url) as client:
            _dask_worker_from_ec2_instance(client, worker_ec2_instance)
            return True
    return False


async def list_unrunnable_tasks(url: AnyUrl) -> list[DaskTask]:
    """
    Raises:
        DaskSchedulerNotFoundError
    """

    def _list_tasks(
        dask_scheduler: distributed.Scheduler,
    ) -> dict[str, dict[str, Any]]:
        return {
            task.key: task.resource_restrictions for task in dask_scheduler.unrunnable
        }

    async with _scheduler_client(url) as client:
        list_of_tasks: dict[
            DaskTaskId, DaskTaskResources
        ] = await _wrap_client_async_routine(client.run_on_scheduler(_list_tasks))
        _logger.debug("found unrunnable tasks: %s", list_of_tasks)
        return [
            DaskTask(task_id=task_id, required_resources=task_resources)
            for task_id, task_resources in list_of_tasks.items()
        ]


async def list_processing_tasks_per_worker(
    url: AnyUrl,
) -> dict[DaskWorkerUrl, list[DaskTask]]:
    """
    Raises:
        DaskSchedulerNotFoundError
    """

    def _list_tasks(
        dask_scheduler: distributed.Scheduler,
    ) -> dict[str, list[tuple[DaskTaskId, DaskTaskResources]]]:
        worker_to_processing_tasks = defaultdict(list)
        for task_key, task_state in dask_scheduler.tasks.items():
            if task_state.processing_on:
                worker_to_processing_tasks[task_state.processing_on.address].append(
                    (task_key, task_state.resource_restrictions)
                )
        return worker_to_processing_tasks

    async with _scheduler_client(url) as client:
        worker_to_tasks: dict[
            str, list[tuple[DaskTaskId, DaskTaskResources]]
        ] = await _wrap_client_async_routine(client.run_on_scheduler(_list_tasks))
        _logger.debug("found processing tasks: %s", worker_to_tasks)
        tasks_per_worker = {}
        for worker, tasks in worker_to_tasks.items():
            tasks_per_worker[worker] = [
                DaskTask(task_id=t[0], required_resources=t[1]) for t in tasks
            ]
        return tasks_per_worker


async def get_worker_still_has_results_in_memory(
    url: AnyUrl, ec2_instance: EC2InstanceData
) -> int:
    """
    Raises:
        DaskSchedulerNotFoundError
        Ec2InvalidDnsNameError
        DaskWorkerNotFoundError
        DaskNoWorkersError
    """
    async with _scheduler_client(url) as client:
        _, worker_details = _dask_worker_from_ec2_instance(client, ec2_instance)

        worker_metrics: dict[str, Any] = worker_details["metrics"]
        return 1 if worker_metrics.get("task_counts") else 0


async def get_worker_used_resources(
    url: AnyUrl, ec2_instance: EC2InstanceData
) -> Resources:
    """
    Raises:
        DaskSchedulerNotFoundError
        Ec2InvalidDnsNameError
        DaskWorkerNotFoundError
        DaskNoWorkersError
    """

    def _get_worker_used_resources(
        dask_scheduler: distributed.Scheduler,
    ) -> dict[str, dict]:
        used_resources: dict[str, dict] = {}
        for worker_name, worker_state in dask_scheduler.workers.items():
            if worker_state.status is distributed.Status.closing_gracefully:
                used_resources[worker_name] = {}
            else:
                used_resources[worker_name] = worker_state.used_resources
        return used_resources

    async with _scheduler_client(url) as client:
        worker_url, _ = _dask_worker_from_ec2_instance(client, ec2_instance)

        # now get the used resources
        used_resources_per_worker: dict[
            str, dict[str, Any]
        ] = await _wrap_client_async_routine(
            client.run_on_scheduler(_get_worker_used_resources)
        )
        if worker_url not in used_resources_per_worker:
            raise DaskWorkerNotFoundError(worker_host=worker_url, url=url)
        worker_used_resources = used_resources_per_worker[worker_url]
        return Resources(
            cpus=worker_used_resources.get("CPU", 0),
            ram=parse_obj_as(ByteSize, worker_used_resources.get("RAM", 0)),
        )


async def compute_cluster_total_resources(
    url: AnyUrl, instances: list[AssociatedInstance]
) -> Resources:
    if not instances:
        return Resources.create_as_empty()
    async with _scheduler_client(url) as client:
        instance_hosts = (
            node_ip_from_ec2_private_dns(i.ec2_instance) for i in instances
        )
        scheduler_info = client.scheduler_info()
        if "workers" not in scheduler_info or not scheduler_info["workers"]:
            raise DaskNoWorkersError(url=url)
        workers: dict[str, Any] = scheduler_info["workers"]
        for worker_details in workers.values():
            if worker_details["host"] not in instance_hosts:
                continue

        return Resources.create_as_empty()


async def try_retire_nodes(url: AnyUrl) -> None:
    async with _scheduler_client(url) as client:
        await _wrap_client_async_routine(
            client.retire_workers(close_workers=False, remove=False)
        )
