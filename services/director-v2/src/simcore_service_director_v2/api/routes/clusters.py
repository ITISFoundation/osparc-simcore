import logging

from fastapi import APIRouter, Depends, HTTPException
from simcore_service_director_v2.modules.dask_clients_pool import DaskClientsPool
from starlette import status

from ...core.errors import ClusterNotFoundError
from ...models.schemas.clusters import ClusterOut
from ...modules.db.repositories.clusters import ClustersRepository
from ..dependencies.dask import get_dask_clients_pool
from ..dependencies.database import get_repository

router = APIRouter()
log = logging.getLogger(__file__)


@router.get(
    "/{cluster_id}",
    summary="Returns the cluster details",
    response_model=ClusterOut,
    status_code=status.HTTP_200_OK,
)
async def get_cluster_with_id(
    cluster_id: int,
    clusters_repo: ClustersRepository = Depends(get_repository(ClustersRepository)),
    dask_clients_pool: DaskClientsPool = Depends(get_dask_clients_pool),
):
    log.debug("Getting details for cluster '%s'", cluster_id)

    try:
        cluster = await clusters_repo.get_cluster(cluster_id)
        async with dask_clients_pool.acquire(cluster) as dask_client:
            scheduler_infos = dask_client.client.scheduler_info()

        return cluster
    except ClusterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{e}") from e
