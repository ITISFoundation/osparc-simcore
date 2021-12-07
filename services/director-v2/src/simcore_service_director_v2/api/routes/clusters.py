import logging

from fastapi import APIRouter, Depends, HTTPException
from models_library.clusters import Cluster
from pydantic.types import NonNegativeInt
from simcore_service_director_v2.api.dependencies.scheduler import (
    get_scheduler_settings,
)
from simcore_service_director_v2.core.settings import DaskSchedulerSettings
from simcore_service_director_v2.modules.dask_clients_pool import DaskClientsPool
from starlette import status

from ...core.errors import ClusterNotFoundError
from ...models.schemas.clusters import ClusterOut, Scheduler
from ...modules.db.repositories.clusters import ClustersRepository
from ..dependencies.dask import get_dask_clients_pool
from ..dependencies.database import get_repository

router = APIRouter()
log = logging.getLogger(__file__)


async def _get_cluster_with_id(
    settings: DaskSchedulerSettings,
    cluster_id: NonNegativeInt,
    clusters_repo: ClustersRepository,
    dask_clients_pool: DaskClientsPool,
) -> ClusterOut:
    log.debug("Getting details for cluster '%s'", cluster_id)
    try:
        cluster: Cluster = dask_clients_pool.default_cluster(settings)
        if cluster_id != settings.DASK_DEFAULT_CLUSTER_ID:
            cluster = await clusters_repo.get_cluster(cluster_id)
        async with dask_clients_pool.acquire(cluster) as client:
            scheduler_info = client.dask_subsystem.client.scheduler_info()
            scheduler_status = client.dask_subsystem.client.status

        return ClusterOut(
            cluster=cluster,
            scheduler=Scheduler(status=scheduler_status, **scheduler_info),
        )
    except ClusterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{e}") from e


@router.get(
    "/default",
    summary="Returns the cluster details",
    response_model=ClusterOut,
    status_code=status.HTTP_200_OK,
)
async def get_default_cluster(
    settings: DaskSchedulerSettings = Depends(get_scheduler_settings),
    clusters_repo: ClustersRepository = Depends(get_repository(ClustersRepository)),
    dask_clients_pool: DaskClientsPool = Depends(get_dask_clients_pool),
):
    assert settings.DASK_DEFAULT_CLUSTER_ID  # nosec
    return await _get_cluster_with_id(
        settings=settings,
        cluster_id=settings.DASK_DEFAULT_CLUSTER_ID,
        clusters_repo=clusters_repo,
        dask_clients_pool=dask_clients_pool,
    )


@router.get(
    "/{cluster_id}",
    summary="Returns the cluster details",
    response_model=ClusterOut,
    status_code=status.HTTP_200_OK,
)
async def get_cluster_with_id(
    cluster_id: NonNegativeInt,
    settings: DaskSchedulerSettings = Depends(get_scheduler_settings),
    clusters_repo: ClustersRepository = Depends(get_repository(ClustersRepository)),
    dask_clients_pool: DaskClientsPool = Depends(get_dask_clients_pool),
):
    return await _get_cluster_with_id(
        settings=settings,
        cluster_id=cluster_id,
        clusters_repo=clusters_repo,
        dask_clients_pool=dask_clients_pool,
    )
