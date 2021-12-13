from fastapi import Request

from ...modules.dask_clients_pool import DaskClientsPool


def get_dask_clients_pool(request: Request) -> DaskClientsPool:
    return DaskClientsPool.instance(request.app)
