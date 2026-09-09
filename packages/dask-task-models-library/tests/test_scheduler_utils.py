import distributed
from dask_task_models_library.scheduler_utils import get_scheduler_details


async def test_get_scheduler_details_returns_all_workers_unlike_scheduler_info():
    """distributed>=2026.7.0: for asynchronous clients, scheduler_info()'s "workers" is
    permanently empty (its periodic background refresh always fetches with n_workers=0, see
    distributed#9308's discussion). get_scheduler_details() uses a live RPC instead."""
    async with (
        distributed.LocalCluster(n_workers=2, processes=False, asynchronous=True) as cluster,
        distributed.Client(cluster, asynchronous=True) as client,
    ):
        assert client.scheduler_info()["workers"] == {}

        scheduler_details = await get_scheduler_details(client)
        assert len(scheduler_details["workers"]) == 2
