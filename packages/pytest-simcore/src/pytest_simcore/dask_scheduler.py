from collections.abc import AsyncIterable, Callable

import pytest
from distributed import Scheduler, SpecCluster, Worker
from yarl import URL


@pytest.fixture
async def dask_spec_local_cluster(
    monkeypatch: pytest.MonkeyPatch,
    unused_tcp_port_factory: Callable,
) -> AsyncIterable[SpecCluster]:
    # in this mode we can precisely create a specific cluster
    workers = {
        "cpu-worker": {
            "cls": Worker,
            "options": {
                "nthreads": 2,
                "resources": {"CPU": 2, "RAM": 48e9},
            },
        },
        "gpu-worker": {
            "cls": Worker,
            "options": {
                "nthreads": 1,
                "resources": {
                    "CPU": 1,
                    "GPU": 1,
                    "RAM": 48e9,
                },
            },
        },
        "bigcpu-worker": {
            "cls": Worker,
            "options": {
                "nthreads": 1,
                "resources": {
                    "CPU": 8,
                    "RAM": 768e9,
                },
            },
        },
    }
    scheduler = {
        "cls": Scheduler,
        "options": {
            "port": unused_tcp_port_factory(),
            "dashboard_address": f":{unused_tcp_port_factory()}",
        },
    }

    async with SpecCluster(
        workers=workers, scheduler=scheduler, asynchronous=True, name="pytest_cluster"
    ) as cluster:
        scheduler_address = URL(cluster.scheduler_address)
        monkeypatch.setenv(
            "COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_URL",
            f"{scheduler_address}" or "invalid",
        )
        yield cluster
