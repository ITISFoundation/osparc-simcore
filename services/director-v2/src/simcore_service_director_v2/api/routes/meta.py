from fastapi import APIRouter

from ...__version__ import __version__, api_version, api_vtag
from ...models.schemas.meta import Meta

router = APIRouter()


@router.get("", response_model=Meta)
async def get_service_metadata():
    return Meta(
        name=__name__.split(".")[0],
        version=api_version,
        released={api_vtag: api_version},
    )
