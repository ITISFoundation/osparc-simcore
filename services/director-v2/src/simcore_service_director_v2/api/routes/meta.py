from fastapi import APIRouter
from models_library.api_schemas_directorv2.meta import Meta, VersionStr

from ...meta import API_VERSION, API_VTAG

router = APIRouter()


@router.get("", response_model=Meta)
async def get_service_metadata() -> Meta:
    return Meta(
        name=__name__.split(".")[0],
        version=VersionStr(API_VERSION),
        released={API_VTAG: VersionStr(API_VERSION), "v0": VersionStr("0.1.0")},
    )
