# pylint:disable=unused-argument,redefined-outer-name

import multiprocessing
from collections import Counter

core_services = ["redis"]


async def test_mpi_locking(loop, simcore_services, redis_service) -> None:
    from simcore_service_sidecar import mpi_lock

    cpu_count = 2

    assert mpi_lock.acquire_mpi_lock(cpu_count) is True
    assert mpi_lock.acquire_mpi_lock(cpu_count) is False


async def test_multiple_parallel_locking(loop, simcore_services, redis_service) -> None:
    from simcore_service_sidecar import mpi_lock

    cpu_count = 3

    def worker(reply_queue: multiprocessing.Queue, cpu_count: int) -> None:
        mpi_lock_acquisition = mpi_lock.acquire_mpi_lock(cpu_count)
        reply_queue.put(mpi_lock_acquisition)

    reply_queue = multiprocessing.Queue()

    for _ in range(10):
        multiprocessing.Process(target=worker, args=(reply_queue, cpu_count)).start()

    results = []
    for _ in range(10):
        results.append(reply_queue.get())

    assert len(results) == 10

    results = Counter(results)
    assert results[True] == 1
    assert results[False] == 9
