from fastapi import APIRouter
from pydantic import parse_obj_as

from ...meta import API_VERSION, API_VTAG
from ...models.schemas.meta import Meta, VersionStr

router = APIRouter()


@router.get("", response_model=Meta)
async def get_service_metadata():
    return Meta(
        name=__name__.split(".")[0],
        version=API_VERSION,
        released={API_VTAG: API_VERSION, "v0": parse_obj_as(VersionStr, "0.1.0")},
    )
