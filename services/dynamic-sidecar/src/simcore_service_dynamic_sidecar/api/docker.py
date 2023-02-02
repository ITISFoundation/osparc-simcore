from fastapi import APIRouter
from pydantic import BaseModel

from ..core.docker_utils import supports_volumes_with_quota

router = APIRouter()


class QuotasCheckResponse(BaseModel):
    are_quotas_supported: bool


@router.post("/docker/quotas:check", response_model=QuotasCheckResponse)
async def are_quotas_supported():
    """
    Checks if docker daemon on the node has supports for volume and disk quotas
    """

    # NOTE: if volumes with quotas are not supported we can say
    # that no quotas for limiting disk space are supported
    return QuotasCheckResponse(are_quotas_supported=await supports_volumes_with_quota())
