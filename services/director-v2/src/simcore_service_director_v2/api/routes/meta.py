from fastapi import APIRouter

from ...meta import API_VERSION, API_VTAG
from ...models.schemas.meta import Meta, VersionStr

router = APIRouter()


@router.get("", response_model=Meta)
async def get_service_metadata() -> Meta:
    return Meta(
        name=__name__.split(".")[0],
        version=VersionStr(API_VERSION),
        released={API_VTAG: VersionStr(API_VERSION), "v0": VersionStr("0.1.0")},
    )
