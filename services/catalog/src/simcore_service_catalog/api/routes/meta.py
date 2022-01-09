from fastapi import APIRouter

from ...meta import API_VERSION, API_VTAG, __version__
from ...models.schemas.meta import Meta

router = APIRouter()


@router.get("", response_model=Meta)
async def get_service_metadata():
    return Meta(
        name=__name__.split(".")[0],
        version=API_VERSION,
        released={API_VTAG: API_VERSION},
    )
