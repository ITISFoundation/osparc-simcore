from fastapi import APIRouter, HTTPException, Response, status

from ..core.docker_utils import supports_volumes_with_quota

router = APIRouter()


@router.post(
    "/docker/quotas:supported",
    summary="Checks if node where sidecar is running quotas for disk and volume space",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_404_NOT_FOUND: {"description": "quotas are not supported"}},
)
async def are_quotas_supported() -> None:
    # NOTE: if volumes with quotas are not supported we can say
    # that no quotas for limiting disk space are supported
    if not await supports_volumes_with_quota():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
