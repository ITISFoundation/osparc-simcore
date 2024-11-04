from fastapi import APIRouter
from models_library.api_schemas__common.meta import BaseMeta

from ..._meta import API_VERSION, API_VTAG

router = APIRouter()


@router.get("", response_model=BaseMeta)
async def get_service_metadata():
    return BaseMeta(
        name=__name__.split(".")[0],
        version=API_VERSION,
        released={API_VTAG: API_VERSION},
    )
