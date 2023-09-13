import logging
from asyncio.log import logger
from typing import Final

from aiocache import cached
from fastapi import APIRouter, Depends, HTTPException
from models_library.api_schemas_directorv2.clusters import (
    ClusterCreate,
    ClusterDetails,
    ClusterDetailsGet,
    ClusterGet,
    ClusterPatch,
    ClusterPing,
)
from models_library.clusters import DEFAULT_CLUSTER_ID, BaseCluster, ClusterID
from models_library.users import UserID
from starlette import status

from ...core.errors import (
    ClusterInvalidOperationError,
    ConfigurationError,
    DaskClientAcquisisitonError,
)
from ...core.settings import ComputationalBackendSettings
from ...modules.dask_clients_pool import DaskClientsPool
from ...modules.db.repositories.clusters import ClustersRepository
from ...utils.dask_client_utils import test_scheduler_endpoint
from ..dependencies.dask import get_dask_clients_pool
from ..dependencies.database import get_repository
from ..dependencies.scheduler import get_scheduler_settings

router = APIRouter()
log = logging.getLogger(__name__)


GET_CLUSTER_DETAILS_CACHING_TTL: Final[int] = 3


def _build_cache_key(fct, *_, **kwargs):
    return f"{fct.__name__}_{kwargs['cluster_id']}"


@cached(ttl=GET_CLUSTER_DETAILS_CACHING_TTL, key_builder=_build_cache_key)
async def _get_cluster_details_with_id(
    settings: ComputationalBackendSettings,
    user_id: UserID,
    cluster_id: ClusterID,
    clusters_repo: ClustersRepository,
    dask_clients_pool: DaskClientsPool,
) -> ClusterDetails:
    log.debug("Getting details for cluster '%s'", cluster_id)
    cluster: BaseCluster = settings.default_cluster
    if cluster_id != DEFAULT_CLUSTER_ID:
        cluster = await clusters_repo.get_cluster(user_id, cluster_id)
    async with dask_clients_pool.acquire(cluster) as client:
        return await client.get_cluster_details()


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


@router.get("", summary="Lists clusters for user", response_model=list[ClusterGet])
async def list_clusters(
    user_id: UserID,
    clusters_repo: ClustersRepository = Depends(get_repository(ClustersRepository)),
    settings: ComputationalBackendSettings = Depends(get_scheduler_settings),
):
    default_cluster = settings.default_cluster
    return [default_cluster] + await clusters_repo.list_clusters(user_id)


@router.get(
    "/default",
    summary="Returns the default cluster",
    response_model=ClusterGet,
    status_code=status.HTTP_200_OK,
)
async def get_default_cluster(
    settings: ComputationalBackendSettings = Depends(get_scheduler_settings),
):
    return settings.default_cluster


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
    settings: ComputationalBackendSettings = Depends(get_scheduler_settings),
    clusters_repo: ClustersRepository = Depends(get_repository(ClustersRepository)),
    dask_clients_pool: DaskClientsPool = Depends(get_dask_clients_pool),
):
    default_cluster = await _get_cluster_details_with_id(
        settings=settings,
        user_id=user_id,
        cluster_id=DEFAULT_CLUSTER_ID,
        clusters_repo=clusters_repo,
        dask_clients_pool=dask_clients_pool,
    )
    logger.debug("found followind %s", f"{default_cluster=!r}")
    return default_cluster


@router.get(
    "/{cluster_id}/details",
    summary="Returns the cluster details",
    response_model=ClusterDetailsGet,
    status_code=status.HTTP_200_OK,
)
async def get_cluster_details(
    user_id: UserID,
    cluster_id: ClusterID,
    settings: ComputationalBackendSettings = Depends(get_scheduler_settings),
    clusters_repo: ClustersRepository = Depends(get_repository(ClustersRepository)),
    dask_clients_pool: DaskClientsPool = Depends(get_dask_clients_pool),
):
    try:
        cluster_details = await _get_cluster_details_with_id(
            settings=settings,
            user_id=user_id,
            cluster_id=cluster_id,
            clusters_repo=clusters_repo,
            dask_clients_pool=dask_clients_pool,
        )
        logger.debug("found following %s", f"{cluster_details=!r}")
        return cluster_details
    except DaskClientAcquisisitonError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{exc}"
        ) from exc


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
        return await test_scheduler_endpoint(
            endpoint=cluster_auth.endpoint, authentication=cluster_auth.authentication
        )

    except ConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{e}"
        ) from e


@router.post(
    "/default:ping",
    summary="Test cluster connection",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def test_default_cluster_connection(
    settings: ComputationalBackendSettings = Depends(get_scheduler_settings),
):
    cluster = settings.default_cluster
    return await test_scheduler_endpoint(
        endpoint=cluster.endpoint, authentication=cluster.authentication
    )


@router.post(
    "/{cluster_id}:ping",
    summary="Test cluster connection",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def test_specific_cluster_connection(
    user_id: UserID,
    cluster_id: ClusterID,
    clusters_repo: ClustersRepository = Depends(get_repository(ClustersRepository)),
):
    cluster = await clusters_repo.get_cluster(user_id, cluster_id)
    return await test_scheduler_endpoint(
        endpoint=cluster.endpoint, authentication=cluster.authentication
    )
