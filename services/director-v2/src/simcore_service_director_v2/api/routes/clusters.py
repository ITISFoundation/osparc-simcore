import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from models_library.clusters import Cluster, ClusterID
from models_library.users import UserID
from pydantic import AnyUrl, parse_obj_as
from simcore_service_director_v2.api.dependencies.scheduler import (
    get_scheduler_settings,
)
from simcore_service_director_v2.utils.dask_client_utils import test_gateway_endpoint
from starlette import status

from ...core.errors import ClusterInvalidOperationError, ConfigurationError
from ...core.settings import DaskSchedulerSettings
from ...models.schemas.clusters import (
    ClusterCreate,
    ClusterDetailsGet,
    ClusterGet,
    ClusterPatch,
    ClusterPing,
    Scheduler,
)
from ...modules.dask_clients_pool import DaskClientsPool
from ...modules.db.repositories.clusters import ClustersRepository
from ..dependencies.dask import get_dask_clients_pool
from ..dependencies.database import get_repository

router = APIRouter()
log = logging.getLogger(__name__)


async def _get_cluster_details_with_id(
    settings: DaskSchedulerSettings,
    user_id: UserID,
    cluster_id: ClusterID,
    clusters_repo: ClustersRepository,
    dask_clients_pool: DaskClientsPool,
) -> ClusterDetailsGet:
    log.debug("Getting details for cluster '%s'", cluster_id)
    cluster: Cluster = dask_clients_pool.default_cluster(settings)
    if cluster_id != settings.DASK_DEFAULT_CLUSTER_ID:
        cluster = await clusters_repo.get_cluster(user_id, cluster_id)
    async with dask_clients_pool.acquire(cluster) as client:
        scheduler_info = client.dask_subsystem.client.scheduler_info()
        scheduler_status = client.dask_subsystem.client.status
        dashboard_link = client.dask_subsystem.client.dashboard_link
    assert dashboard_link  # nosec
    return ClusterDetailsGet(
        scheduler=Scheduler(status=scheduler_status, **scheduler_info),
        dashboard_link=parse_obj_as(AnyUrl, dashboard_link),
    )


@router.post(
    "",
    summary="Create a new cluster for a user",
    response_model=ClusterGet,
    status_code=status.HTTP_201_CREATED,
)
async def create_cluster(
    user_id: UserID,
    new_cluster: ClusterCreate,
    clusters_repo: ClustersRepository = Depends(get_repository(ClustersRepository)),
):
    return await clusters_repo.create_cluster(user_id, new_cluster)


@router.get("", summary="Lists clusters for user", response_model=List[ClusterGet])
async def list_clusters(
    user_id: UserID,
    clusters_repo: ClustersRepository = Depends(get_repository(ClustersRepository)),
):
    return await clusters_repo.list_clusters(user_id)


@router.get(
    "/default",
    summary="Returns the default cluster",
    response_model=ClusterGet,
    status_code=status.HTTP_200_OK,
)
async def get_default_cluster(
    settings: DaskSchedulerSettings = Depends(get_scheduler_settings),
):
    assert settings.DASK_DEFAULT_CLUSTER_ID is not None  # nosec
    raise NotImplementedError("dev in progress")


@router.get(
    "/{cluster_id}",
    summary="Get one cluster for user",
    response_model=ClusterGet,
    status_code=status.HTTP_200_OK,
)
async def get_cluster(
    user_id: UserID,
    cluster_id: ClusterID,
    clusters_repo: ClustersRepository = Depends(get_repository(ClustersRepository)),
):
    return await clusters_repo.get_cluster(user_id, cluster_id)


@router.patch(
    "/{cluster_id}",
    summary="Modify a cluster for user",
    response_model=ClusterGet,
    status_code=status.HTTP_200_OK,
)
async def update_cluster(
    user_id: UserID,
    cluster_id: ClusterID,
    updated_cluster: ClusterPatch,
    clusters_repo: ClustersRepository = Depends(get_repository(ClustersRepository)),
):
    try:
        return await clusters_repo.update_cluster(user_id, cluster_id, updated_cluster)
    except ClusterInvalidOperationError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{e}") from e


@router.delete(
    "/{cluster_id}",
    summary="Remove a cluster for user",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_cluster(
    user_id: UserID,
    cluster_id: ClusterID,
    clusters_repo: ClustersRepository = Depends(get_repository(ClustersRepository)),
):
    await clusters_repo.delete_cluster(user_id, cluster_id)


@router.get(
    "/default/details",
    summary="Returns the cluster details",
    response_model=ClusterDetailsGet,
    status_code=status.HTTP_200_OK,
)
async def get_default_cluster_details(
    user_id: UserID,
    settings: DaskSchedulerSettings = Depends(get_scheduler_settings),
    clusters_repo: ClustersRepository = Depends(get_repository(ClustersRepository)),
    dask_clients_pool: DaskClientsPool = Depends(get_dask_clients_pool),
):
    assert settings.DASK_DEFAULT_CLUSTER_ID is not None  # nosec
    return await _get_cluster_details_with_id(
        settings=settings,
        user_id=user_id,
        cluster_id=settings.DASK_DEFAULT_CLUSTER_ID,
        clusters_repo=clusters_repo,
        dask_clients_pool=dask_clients_pool,
    )


@router.get(
    "/{cluster_id}/details",
    summary="Returns the cluster details",
    response_model=ClusterDetailsGet,
    status_code=status.HTTP_200_OK,
)
async def get_cluster_details(
    user_id: UserID,
    cluster_id: ClusterID,
    settings: DaskSchedulerSettings = Depends(get_scheduler_settings),
    clusters_repo: ClustersRepository = Depends(get_repository(ClustersRepository)),
    dask_clients_pool: DaskClientsPool = Depends(get_dask_clients_pool),
):
    return await _get_cluster_details_with_id(
        settings=settings,
        user_id=user_id,
        cluster_id=cluster_id,
        clusters_repo=clusters_repo,
        dask_clients_pool=dask_clients_pool,
    )


@router.post(
    ":ping",
    summary="Test cluster connection",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def test_cluster_connection(
    cluster_auth: ClusterPing,
):
    try:
        return await test_gateway_endpoint(
            endpoint=cluster_auth.endpoint, authentication=cluster_auth.authentication
        )

    except ConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{e}"
        ) from e
