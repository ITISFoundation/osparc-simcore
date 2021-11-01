# pylint:disable=unused-argument,redefined-outer-name

import multiprocessing
from collections import Counter

import pytest
from simcore_service_sidecar import mpi_lock

pytest_simcore_core_services_selection = ["redis"]


@pytest.fixture
def redis_service_config(redis_service) -> None:
    old_config = mpi_lock.config.CELERY_CONFIG.redis
    mpi_lock.config.CELERY_CONFIG.redis = redis_service

    yield

    mpi_lock.config.CELERY_CONFIG.redis = old_config


async def test_mpi_locking(loop, simcore_services_ready, redis_service_config) -> None:
    cpu_count = 2

    assert mpi_lock.acquire_mpi_lock(cpu_count) is True
    assert mpi_lock.acquire_mpi_lock(cpu_count) is False


@pytest.mark.parametrize("process_count, cpu_count", [(1, 3), (32, 4)])
async def test_multiple_parallel_locking(
    loop, simcore_services_ready, redis_service_config, process_count, cpu_count
) -> None:
    def worker(reply_queue: multiprocessing.Queue, cpu_count: int) -> None:
        mpi_lock_acquisition = mpi_lock.acquire_mpi_lock(cpu_count)
        reply_queue.put(mpi_lock_acquisition)

    reply_queue = multiprocessing.Queue()

    for _ in range(process_count):
        multiprocessing.Process(target=worker, args=(reply_queue, cpu_count)).start()

    results = []
    for _ in range(process_count):
        results.append(reply_queue.get())

    assert len(results) == process_count

    results = Counter(results)
    assert results[True] == 1
    assert results[False] == process_count - 1
