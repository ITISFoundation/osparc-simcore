import collections
import contextlib
import logging
import re
from collections import defaultdict
from collections.abc import AsyncIterator, Coroutine
from typing import Any, Final, TypeAlias, TypedDict

import dask.typing
import distributed
from aws_library.ec2 import EC2InstanceData, Resources
from aws_library.ec2._models import EC2InstanceType
from dask_task_models_library.resource_constraints import (
    DASK_WORKER_THREAD_RESOURCE_NAME,
    DaskTaskResources,
    create_ec2_resource_constraint_key,
)
from distributed.core import Status
from models_library.clusters import ClusterAuthentication, TLSAuthentication
from pydantic import AnyUrl

from ..core.errors import (
    DaskNoWorkersError,
    DaskSchedulerNotFoundError,
    DaskWorkerNotFoundError,
)
from ..core.settings import DaskMonitoringSettings
from ..models import DaskTask, DaskTaskId
from ..utils.utils_ec2 import (
    node_host_name_from_ec2_private_dns,
    node_ip_from_ec2_private_dns,
)
from .cluster_scaling._utils_computational import (
    DASK_TO_RESOURCE_NAME_MAPPING,
)

_logger = logging.getLogger(__name__)


async def _wrap_client_async_routine(
    client_coroutine: Coroutine[Any, Any, Any] | Any | None,
) -> Any:
    """Dask async behavior does not go well with Pylance as it returns
    a union of types. this wrapper makes both mypy and pylance happy"""
    assert client_coroutine  # nosec
    return await client_coroutine


_DASK_SCHEDULER_CONNECT_TIMEOUT_S: Final[int] = 5


@contextlib.asynccontextmanager
async def _scheduler_client(url: AnyUrl, authentication: ClusterAuthentication) -> AsyncIterator[distributed.Client]:
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
        dask_worker: tuple[DaskWorkerUrl, DaskWorkerDetails],
    ) -> bool:
        _, details = dask_worker
        if match := re.match(DASK_NAME_PATTERN, details["name"]):
            return bool(match.group("private_ip") == node_hostname)
        _logger.error(
            "Unexpected worker name format: %s. TIP: this should be investigated as this is unexpected",
            details["name"],
        )
        return False

    filtered_workers = dict(filter(_find_by_worker_host, workers.items()))
    if not filtered_workers:
        raise DaskWorkerNotFoundError(worker_host=ec2_instance.aws_private_dns, url=client.scheduler.address)
    assert len(filtered_workers) == 1, f"returned workers {filtered_workers}, {node_hostname=}"  # nosec
    return next(iter(filtered_workers.items()))


class _DaskClusterTasks(TypedDict):
    processing: dict[DaskWorkerUrl, list[tuple[dask.typing.Key, DaskTaskResources]]]
    unrunnable: dict[dask.typing.Key, DaskTaskResources]


async def _list_cluster_known_tasks(
    client: distributed.Client,
) -> _DaskClusterTasks:
    def _list_on_scheduler(
        dask_scheduler: distributed.Scheduler,
    ) -> dict[str, Any]:
        # NOTE: _DaskClusterTasks uses cannot be used here because of serialization issues
        worker_to_processing_tasks = defaultdict(list)
        unrunnable_tasks = {}
        for task_key, task_state in dask_scheduler.tasks.items():
            if task_state.processing_on:
                worker_to_processing_tasks[task_state.processing_on.address].append(
                    (
                        task_key,
                        (task_state.resource_restrictions or {}) | {DASK_WORKER_THREAD_RESOURCE_NAME: 1},
                    )
                )
            elif task_state in dask_scheduler.unrunnable:
                unrunnable_tasks[task_key] = (task_state.resource_restrictions or {}) | {
                    DASK_WORKER_THREAD_RESOURCE_NAME: 1
                }

        return {
            "processing": worker_to_processing_tasks,
            "unrunnable": unrunnable_tasks,
        }

    list_of_tasks: _DaskClusterTasks = await client.run_on_scheduler(_list_on_scheduler)
    _logger.debug("found tasks: %s", list_of_tasks)

    return list_of_tasks


async def is_worker_connected(
    scheduler_url: AnyUrl,
    authentication: ClusterAuthentication,
    worker_ec2_instance: EC2InstanceData,
) -> bool:
    with contextlib.suppress(DaskNoWorkersError, DaskWorkerNotFoundError):
        async with _scheduler_client(scheduler_url, authentication) as client:
            _, worker_details = _dask_worker_from_ec2_instance(client, worker_ec2_instance)
            return Status(worker_details["status"]) == Status.running
    return False


async def is_worker_retired(
    scheduler_url: AnyUrl,
    authentication: ClusterAuthentication,
    worker_ec2_instance: EC2InstanceData,
) -> bool:
    with contextlib.suppress(DaskNoWorkersError, DaskWorkerNotFoundError):
        async with _scheduler_client(scheduler_url, authentication) as client:
            _, worker_details = _dask_worker_from_ec2_instance(client, worker_ec2_instance)
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
    authentication: ClusterAuthentication,
) -> list[DaskTask]:
    """
    Raises:
        DaskSchedulerNotFoundError
    """

    async with _scheduler_client(scheduler_url, authentication) as client:
        known_tasks = await _list_cluster_known_tasks(client)
        list_of_tasks = known_tasks["unrunnable"]

        return [
            DaskTask(
                task_id=_dask_key_to_dask_task_id(task_id),
                required_resources=task_resources,
            )
            for task_id, task_resources in list_of_tasks.items()
        ]


async def list_processing_tasks_per_worker(
    scheduler_url: AnyUrl,
    authentication: ClusterAuthentication,
) -> dict[DaskWorkerUrl, list[DaskTask]]:
    """
    Raises:
        DaskSchedulerNotFoundError
    """

    async with _scheduler_client(scheduler_url, authentication) as client:
        worker_to_tasks = await _list_cluster_known_tasks(client)

        tasks_per_worker = defaultdict(list)
        for worker, tasks in worker_to_tasks["processing"].items():
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
    authentication: ClusterAuthentication,
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
    authentication: ClusterAuthentication,
    ec2_instance: EC2InstanceData,
) -> Resources:
    """
    Raises:
        DaskSchedulerNotFoundError
        Ec2InvalidDnsNameError
        DaskWorkerNotFoundError
        DaskNoWorkersError
    """

    async with _scheduler_client(scheduler_url, authentication) as client:
        worker_url, _ = _dask_worker_from_ec2_instance(client, ec2_instance)
        known_tasks = await _list_cluster_known_tasks(client)
        worker_processing_tasks = known_tasks["processing"].get(worker_url, [])
        if not worker_processing_tasks:
            return Resources.create_as_empty()

        total_resources_used: collections.Counter = collections.Counter()
        for _, task_resources in worker_processing_tasks:
            total_resources_used.update(task_resources)

        _logger.debug("found %s for %s", f"{total_resources_used=}", f"{worker_url=}")
        return Resources.from_flat_dict(dict(total_resources_used), mapping=DASK_TO_RESOURCE_NAME_MAPPING)


async def compute_cluster_total_resources(
    scheduler_url: AnyUrl,
    authentication: ClusterAuthentication,
    instances: list[EC2InstanceData],
) -> Resources:
    if not instances:
        return Resources.create_as_empty()
    async with _scheduler_client(scheduler_url, authentication) as client:
        ec2_instance_resources_map = {node_ip_from_ec2_private_dns(i): i.resources for i in instances}
        scheduler_info = client.scheduler_info()
        if "workers" not in scheduler_info or not scheduler_info["workers"]:
            raise DaskNoWorkersError(url=scheduler_url)
        workers: dict[str, Any] = scheduler_info["workers"]
        cluster_resources = Resources.create_as_empty()
        for worker_details in workers.values():
            if worker_details["host"] not in ec2_instance_resources_map:
                continue
            # get dask information about resources
            worker_dask_resources = worker_details["resources"]
            worker_dask_nthreads = worker_details["nthreads"]
            cluster_resources += Resources.from_flat_dict(
                {
                    **worker_dask_resources,
                    DASK_WORKER_THREAD_RESOURCE_NAME: worker_dask_nthreads,
                },
                mapping=DASK_TO_RESOURCE_NAME_MAPPING,
            )

        return cluster_resources


async def try_retire_nodes(scheduler_url: AnyUrl, authentication: ClusterAuthentication) -> None:
    async with _scheduler_client(scheduler_url, authentication) as client:
        await _wrap_client_async_routine(client.retire_workers(close_workers=False, remove=False))


_LARGE_RESOURCE: Final[int] = 99999


def add_instance_generic_resources(settings: DaskMonitoringSettings, instance: EC2InstanceData) -> None:
    instance_threads = max(1, round(instance.resources.cpus))
    if settings.DASK_NTHREADS > 0:
        # this overrides everything
        instance_threads = settings.DASK_NTHREADS
    if settings.DASK_NTHREADS_MULTIPLIER > 1:
        instance_threads = instance_threads * settings.DASK_NTHREADS_MULTIPLIER
    instance.resources.generic_resources[DASK_WORKER_THREAD_RESOURCE_NAME] = instance_threads

    instance.resources.generic_resources[create_ec2_resource_constraint_key(instance.type)] = _LARGE_RESOURCE


def add_instance_type_generic_resource(settings: DaskMonitoringSettings, instance_type: EC2InstanceType) -> None:
    instance_threads = max(1, round(instance_type.resources.cpus))
    if settings.DASK_NTHREADS > 0:
        # this overrides everything
        instance_threads = settings.DASK_NTHREADS
    if settings.DASK_NTHREADS_MULTIPLIER > 1:
        instance_threads = instance_threads * settings.DASK_NTHREADS_MULTIPLIER

    instance_type.resources.generic_resources[DASK_WORKER_THREAD_RESOURCE_NAME] = instance_threads

    instance_type.resources.generic_resources[create_ec2_resource_constraint_key(instance_type.name)] = _LARGE_RESOURCE
