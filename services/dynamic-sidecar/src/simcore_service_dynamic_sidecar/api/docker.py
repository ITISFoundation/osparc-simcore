from fastapi import APIRouter, status

from ..core.docker_utils import supports_volumes_with_quota

router = APIRouter()


@router.post(
    "/docker/quotas",
    summary="Checks if docker daemon on the node has supports for volume and disk quotas",
    status_code=status.HTTP_200_OK,
)
async def are_quotas_supported() -> dict[str, bool]:
    # NOTE: if volumes with quotas are not supported we can say
    # that no quotas for limiting disk space are supported
    return dict(are_quotas_supported=await supports_volumes_with_quota())
