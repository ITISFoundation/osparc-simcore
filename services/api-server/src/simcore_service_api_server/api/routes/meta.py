from typing import Union

from fastapi import APIRouter

from ...__version__ import __version__, api_version, api_vtag
from ...models.schemas.meta import Meta, VersionStr

router = APIRouter()


@router.get("", response_model=Union[Meta, VersionStr])
async def get_service_metadata(extended_info: bool = False):
    return (
        Meta(
            name=__name__.split(".")[0],
            version=api_version,
            released={api_vtag: api_version},
        )
        if extended_info
        else api_version
    )
