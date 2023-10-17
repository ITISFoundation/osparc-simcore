import contextlib
import logging
from collections.abc import AsyncIterator, Coroutine
from typing import Any, Final

import distributed
from pydantic import AnyUrl, ByteSize, parse_obj_as

from ..core.errors import DaskSchedulerNotFoundError, DaskWorkerNotFoundError
from ..models import (
    AssociatedInstance,
    DaskTask,
    DaskTaskId,
    DaskTaskResources,
    EC2InstanceData,
    Resources,
)
from ..utils.auto_scaling_core import node_ip_from_ec2_private_dns

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
        _logger.info("found unrunnable tasks: %s", list_of_tasks)
        return [
            DaskTask(task_id=task_id, required_resources=task_resources)
            for task_id, task_resources in list_of_tasks.items()
        ]


async def list_processing_tasks(url: AnyUrl) -> list[DaskTaskId]:
    """
    Raises:
        DaskSchedulerNotFoundError
    """
    async with _scheduler_client(url) as client:
        processing_tasks = set()
        if worker_to_processing_tasks := await _wrap_client_async_routine(
            client.processing()
        ):
            _logger.info("cluster worker processing: %s", worker_to_processing_tasks)
            for tasks in worker_to_processing_tasks.values():
                processing_tasks |= set(tasks)

        return list(processing_tasks)


DaskWorkerUrl = str
DaskWorkerDetails = dict[str, Any]


def _dask_worker_from_ec2_instance(
    client: distributed.Client, ec2_instance: EC2InstanceData
) -> tuple[DaskWorkerUrl, DaskWorkerDetails]:
    """
    Raises:
        Ec2InvalidDnsNameError
        DaskWorkerNotFoundError
    """
    node_ip = node_ip_from_ec2_private_dns(ec2_instance)
    scheduler_info = client.scheduler_info()
    assert client.scheduler  # nosec
    if "workers" not in scheduler_info or not scheduler_info["workers"]:
        raise DaskWorkerNotFoundError(url=client.scheduler.address)
    workers: dict[DaskWorkerUrl, DaskWorkerDetails] = scheduler_info["workers"]

    # dict is of type dask_worker_address: worker_details
    def _find_by_worker_host(
        dask_worker: tuple[DaskWorkerUrl, DaskWorkerDetails]
    ) -> bool:
        _, details = dask_worker
        return details["host"] == node_ip

    filtered_workers = dict(filter(_find_by_worker_host, workers.items()))
    if not filtered_workers:
        raise DaskWorkerNotFoundError(url=client.scheduler.address)
    return next(iter(filtered_workers.items()))


async def get_worker_still_has_results_in_memory(
    url: AnyUrl, ec2_instance: EC2InstanceData
) -> int:
    """
    Raises:
        DaskSchedulerNotFoundError
        Ec2InvalidDnsNameError
        DaskWorkerNotFoundError: if there are no workers or no worker corresponding to ec2_instance
    """
    async with _scheduler_client(url) as client:
        _, worker_details = _dask_worker_from_ec2_instance(client, ec2_instance)

        worker_metrics: dict[str, Any] = worker_details["metrics"]
        if worker_metrics.get("task_counts", {}) != {}:
            return 1
    return 0


async def get_worker_used_resources(
    url: AnyUrl, ec2_instance: EC2InstanceData
) -> Resources:
    """
    Raises:
        DaskSchedulerNotFoundError
        Ec2InvalidDnsNameError
        DaskWorkerNotFoundError: if there are no workers or no worker corresponding to ec2_instance
    """

    def _get_worker_used_resources(
        dask_scheduler: distributed.Scheduler,
    ) -> dict[str, dict]:
        used_resources = {}
        for worker_name, worker_state in dask_scheduler.workers.items():
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
            raise DaskWorkerNotFoundError(url=url)
        worker_used_resources = used_resources_per_worker[worker_url]
        return Resources(
            cpus=worker_used_resources.get("CPU", 0),
            ram=parse_obj_as(ByteSize, worker_used_resources.get("RAM", 0)),
        )


async def compute_cluster_total_resources(
    url: AnyUrl, instances: list[AssociatedInstance]
) -> Resources:
    async with _scheduler_client(url) as client:
        instance_hosts = (
            node_ip_from_ec2_private_dns(i.ec2_instance) for i in instances
        )
        scheduler_info = client.scheduler_info()
        if "workers" not in scheduler_info or not scheduler_info["workers"]:
            raise DaskWorkerNotFoundError(url=url)
        workers: dict[str, Any] = scheduler_info["workers"]
        for worker_details in workers.values():
            if worker_details["host"] not in instance_hosts:
                continue

        return Resources.create_as_empty()
