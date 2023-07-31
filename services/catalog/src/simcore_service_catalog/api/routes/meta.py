from fastapi import APIRouter
from models_library.api_schemas_catalog.meta import Meta, VersionStr
from pydantic import parse_obj_as

from ..._meta import API_VERSION, API_VTAG

router = APIRouter()


@router.get("", response_model=Meta)
async def get_service_metadata():
    return Meta(
        name=__name__.split(".")[0],
        version=parse_obj_as(VersionStr, API_VERSION),
        released={API_VTAG: parse_obj_as(VersionStr, API_VERSION)},
    )
