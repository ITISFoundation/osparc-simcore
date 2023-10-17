# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterable, AsyncIterator, Callable
from typing import Any

import distributed
import pytest
from yarl import URL


@pytest.fixture
def dask_workers_config() -> dict[str, Any]:
    return {
        "cpu-worker": {
            "cls": distributed.Worker,
            "options": {
                "nthreads": 2,
                "resources": {"CPU": 2, "RAM": 48e9},
            },
        },
        "gpu-worker": {
            "cls": distributed.Worker,
            "options": {
                "nthreads": 1,
                "resources": {
                    "CPU": 1,
                    "GPU": 1,
                    "RAM": 48e9,
                },
            },
        },
        "large-ram-worker": {
            "cls": distributed.Worker,
            "options": {
                "nthreads": 1,
                "resources": {
                    "CPU": 8,
                    "RAM": 768e9,
                },
            },
        },
    }


@pytest.fixture
def dask_scheduler_config(
    unused_tcp_port_factory: Callable,
) -> dict[str, Any]:
    return {
        "cls": distributed.Scheduler,
        "options": {
            "port": unused_tcp_port_factory(),
            "dashboard_address": f":{unused_tcp_port_factory()}",
        },
    }


@pytest.fixture
async def dask_spec_local_cluster(
    monkeypatch: pytest.MonkeyPatch,
    dask_workers_config: dict[str, Any],
    dask_scheduler_config: dict[str, Any],
) -> AsyncIterator[distributed.SpecCluster]:
    # in this mode we can precisely create a specific cluster

    async with distributed.SpecCluster(
        workers=dask_workers_config,
        scheduler=dask_scheduler_config,
        asynchronous=True,
        name="pytest_cluster",
    ) as cluster:
        scheduler_address = URL(cluster.scheduler_address)
        monkeypatch.setenv(
            "COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_URL",
            f"{scheduler_address}" or "invalid",
        )
        yield cluster


@pytest.fixture
async def dask_local_cluster_without_workers(
    monkeypatch: pytest.MonkeyPatch,
    dask_scheduler_config: dict[str, Any],
) -> AsyncIterable[distributed.SpecCluster]:
    # in this mode we can precisely create a specific cluster

    async with distributed.SpecCluster(
        scheduler=dask_scheduler_config,
        asynchronous=True,
        name="pytest_cluster_no_workers",
    ) as cluster:
        scheduler_address = URL(cluster.scheduler_address)
        monkeypatch.setenv(
            "COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_URL",
            f"{scheduler_address}" or "invalid",
        )
        yield cluster


@pytest.fixture
async def dask_spec_cluster_client(
    dask_spec_local_cluster: distributed.SpecCluster,
) -> AsyncIterator[distributed.Client]:
    async with distributed.Client(
        dask_spec_local_cluster.scheduler_address, asynchronous=True
    ) as client:
        yield client
