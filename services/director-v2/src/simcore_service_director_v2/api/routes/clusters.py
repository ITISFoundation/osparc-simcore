import logging

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from ...core.errors import ClusterNotFoundError
from ...models.schemas.clusters import ClusterOut
from ...modules.db.repositories.clusters import ClustersRepository
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
):
    log.debug("Getting details for cluster '%s'", cluster_id)

    try:
        cluster = await clusters_repo.get_cluster(cluster_id)
    except ClusterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{e}") from e
