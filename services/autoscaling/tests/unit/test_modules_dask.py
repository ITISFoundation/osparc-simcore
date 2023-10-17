# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
from collections.abc import Callable
from typing import Any, Final

import distributed
import pytest
from faker import Faker
from pydantic import AnyUrl, ByteSize, parse_obj_as
from simcore_service_autoscaling.core.errors import (
    DaskSchedulerNotFoundError,
    DaskWorkerNotFoundError,
    Ec2InvalidDnsNameError,
)
from simcore_service_autoscaling.models import (
    DaskTaskId,
    DaskTaskResources,
    EC2InstanceData,
    Resources,
)
from simcore_service_autoscaling.modules.dask import (
    DaskTask,
    _scheduler_client,
    get_worker_still_has_results_in_memory,
    get_worker_used_resources,
    list_processing_tasks,
    list_unrunnable_tasks,
)
from tenacity import retry, stop_after_delay, wait_fixed


async def test__scheduler_client_with_wrong_url(faker: Faker):
    with pytest.raises(DaskSchedulerNotFoundError):
        async with _scheduler_client(
            parse_obj_as(AnyUrl, f"tcp://{faker.ipv4()}:{faker.port_number()}")
        ):
            ...


@pytest.fixture
def scheduler_url(dask_spec_local_cluster: distributed.SpecCluster) -> AnyUrl:
    return parse_obj_as(AnyUrl, dask_spec_local_cluster.scheduler_address)


@pytest.fixture
def dask_workers_config() -> dict[str, Any]:
    # NOTE: override of pytest-simcore dask_workers_config to have only 1 worker
    return {
        "single-cpu-worker": {
            "cls": distributed.Worker,
            "options": {
                "nthreads": 2,
                "resources": {"CPU": 2, "RAM": 48e9},
            },
        }
    }


async def test__scheduler_client(scheduler_url: AnyUrl):
    async with _scheduler_client(scheduler_url):
        ...


async def test_list_unrunnable_tasks_with_no_workers(
    dask_local_cluster_without_workers: distributed.SpecCluster,
):
    scheduler_url = parse_obj_as(
        AnyUrl, dask_local_cluster_without_workers.scheduler_address
    )
    assert await list_unrunnable_tasks(scheduler_url) == []


async def test_list_unrunnable_tasks(
    scheduler_url: AnyUrl,
    create_dask_task: Callable[[DaskTaskResources], distributed.Future],
):
    # we have nothing running now
    assert await list_unrunnable_tasks(scheduler_url) == []
    # start a task that cannot run
    dask_task_impossible_resources = {"XRAM": 213}
    future = create_dask_task(dask_task_impossible_resources)
    assert future
    assert await list_unrunnable_tasks(scheduler_url) == [
        DaskTask(task_id=future.key, required_resources=dask_task_impossible_resources)
    ]
    # remove that future, will remove the task
    del future
    assert await list_unrunnable_tasks(scheduler_url) == []


_REMOTE_FCT_SLEEP_TIME_S: Final[int] = 3


async def test_list_processing_tasks(
    scheduler_url: AnyUrl,
    dask_spec_cluster_client: distributed.Client,
):
    def _add_fct(x: int, y: int) -> int:
        import time

        time.sleep(_REMOTE_FCT_SLEEP_TIME_S)
        return x + y

    # there is nothing now
    assert await list_processing_tasks(url=scheduler_url) == []

    # this function will be queued and executed as there are no specific resources needed
    future_queued_task = dask_spec_cluster_client.submit(_add_fct, 2, 5)
    assert future_queued_task

    assert await list_processing_tasks(scheduler_url) == [
        DaskTaskId(future_queued_task.key)
    ]

    result = await future_queued_task.result(timeout=_REMOTE_FCT_SLEEP_TIME_S + 4)  # type: ignore
    assert result == 7

    # nothing processing anymore
    assert await list_processing_tasks(url=scheduler_url) == []


_DASK_SCHEDULER_REACTION_TIME_S: Final[int] = 4


@retry(stop=stop_after_delay(_DASK_SCHEDULER_REACTION_TIME_S), wait=wait_fixed(1))
async def _wait_for_task_done(future: distributed.Future) -> None:
    assert future.done() is True


async def _wait_for_dask_scheduler_to_change_state() -> None:
    # NOTE: I know this is kind of stupid
    await asyncio.sleep(_DASK_SCHEDULER_REACTION_TIME_S)


@pytest.fixture
def fake_ec2_instance_data_with_invalid_ec2_name(
    fake_ec2_instance_data: Callable[..., EC2InstanceData], faker: Faker
) -> EC2InstanceData:
    return fake_ec2_instance_data(aws_private_dns=faker.name())


async def test_get_worker_still_has_results_in_memory_with_invalid_ec2_name_raises(
    scheduler_url: AnyUrl,
    fake_ec2_instance_data_with_invalid_ec2_name: EC2InstanceData,
):
    with pytest.raises(Ec2InvalidDnsNameError):
        await get_worker_still_has_results_in_memory(
            scheduler_url, fake_ec2_instance_data_with_invalid_ec2_name
        )


async def test_get_worker_still_has_results_in_memory_with_no_workers_raises(
    dask_local_cluster_without_workers: distributed.SpecCluster,
    fake_localhost_ec2_instance_data: EC2InstanceData,
):
    scheduler_url = parse_obj_as(
        AnyUrl, dask_local_cluster_without_workers.scheduler_address
    )
    with pytest.raises(DaskWorkerNotFoundError):
        await get_worker_still_has_results_in_memory(
            scheduler_url, fake_localhost_ec2_instance_data
        )


async def test_get_worker_still_has_results_in_memory_with_invalid_worker_host_raises(
    scheduler_url: AnyUrl,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    ec2_instance_data = fake_ec2_instance_data()
    with pytest.raises(DaskWorkerNotFoundError):
        await get_worker_still_has_results_in_memory(scheduler_url, ec2_instance_data)


@pytest.mark.parametrize("fct_shall_err", [True, False], ids=str)
async def test_get_worker_still_has_results_in_memory(
    scheduler_url: AnyUrl,
    dask_spec_cluster_client: distributed.Client,
    fake_localhost_ec2_instance_data: EC2InstanceData,
    fct_shall_err: bool,
):
    # nothing ran, so it's 0
    assert (
        await get_worker_still_has_results_in_memory(
            scheduler_url, fake_localhost_ec2_instance_data
        )
        == 0
    )

    # now run something quickly
    def _add_fct(x: int, y: int) -> int:
        if fct_shall_err:
            msg = "BAM"
            raise RuntimeError(msg)
        return x + y

    # this will run right away and remain in memory until we fetch it
    future_queued_task = dask_spec_cluster_client.submit(_add_fct, 2, 5)
    assert future_queued_task
    await _wait_for_task_done(future_queued_task)
    assert (
        await get_worker_still_has_results_in_memory(
            scheduler_url, fake_localhost_ec2_instance_data
        )
        == 1
    )

    # get the result will NOT bring the data back
    if fct_shall_err:
        exc = await future_queued_task.exception(  # type: ignore
            timeout=_DASK_SCHEDULER_REACTION_TIME_S
        )
        assert isinstance(exc, RuntimeError)
    else:
        result = await future_queued_task.result(timeout=_DASK_SCHEDULER_REACTION_TIME_S)  # type: ignore
        assert result == 7

    await _wait_for_dask_scheduler_to_change_state()
    assert (
        await get_worker_still_has_results_in_memory(
            scheduler_url, fake_localhost_ec2_instance_data
        )
        == 1
    )

    # this should remove the memory
    del future_queued_task
    await _wait_for_dask_scheduler_to_change_state()
    assert (
        await get_worker_still_has_results_in_memory(
            scheduler_url, fake_localhost_ec2_instance_data
        )
        == 0
    )


async def test_worker_used_resources_with_invalid_ec2_name_raises(
    scheduler_url: AnyUrl,
    fake_ec2_instance_data_with_invalid_ec2_name: EC2InstanceData,
):
    with pytest.raises(Ec2InvalidDnsNameError):
        await get_worker_used_resources(
            scheduler_url, fake_ec2_instance_data_with_invalid_ec2_name
        )


async def test_worker_used_resources_with_no_workers_raises(
    dask_local_cluster_without_workers: distributed.SpecCluster,
    fake_localhost_ec2_instance_data: EC2InstanceData,
):
    scheduler_url = parse_obj_as(
        AnyUrl, dask_local_cluster_without_workers.scheduler_address
    )
    with pytest.raises(DaskWorkerNotFoundError):
        await get_worker_used_resources(scheduler_url, fake_localhost_ec2_instance_data)


async def test_worker_used_resources_with_invalid_worker_host_raises(
    scheduler_url: AnyUrl,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    ec2_instance_data = fake_ec2_instance_data()
    with pytest.raises(DaskWorkerNotFoundError):
        await get_worker_used_resources(scheduler_url, ec2_instance_data)


async def test_worker_used_resources(
    scheduler_url: AnyUrl,
    dask_spec_cluster_client: distributed.Client,
    fake_localhost_ec2_instance_data: EC2InstanceData,
):
    # initial state
    assert (
        await get_worker_used_resources(scheduler_url, fake_localhost_ec2_instance_data)
        == Resources.create_as_empty()
    )

    def _add_fct(x: int, y: int) -> int:
        import time

        time.sleep(_DASK_SCHEDULER_REACTION_TIME_S * 2)
        return x + y

    # run something that uses resources
    num_cpus = 2
    future_queued_task = dask_spec_cluster_client.submit(
        _add_fct, 2, 5, resources={"CPU": num_cpus}
    )
    assert future_queued_task
    await _wait_for_dask_scheduler_to_change_state()
    assert await get_worker_used_resources(
        scheduler_url, fake_localhost_ec2_instance_data
    ) == Resources(cpus=num_cpus, ram=ByteSize(0))

    result = await future_queued_task.result(timeout=_DASK_SCHEDULER_REACTION_TIME_S)  # type: ignore
    assert result == 7

    # back to no use
    assert (
        await get_worker_used_resources(scheduler_url, fake_localhost_ec2_instance_data)
        == Resources.create_as_empty()
    )
