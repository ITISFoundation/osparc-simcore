# pylint:disable=unused-argument,redefined-outer-name

import multiprocessing

core_services = ["redis"]


async def test_mpi_locking(loop, redis_service):
    from simcore_service_sidecar import mpi_lock

    cpu_count = multiprocessing.cpu_count()
    assert mpi_lock.acquire_mpi_lock(cpu_count) is True
    assert mpi_lock.acquire_mpi_lock(cpu_count) is False
