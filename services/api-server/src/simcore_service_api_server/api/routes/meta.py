from typing import Callable

from fastapi import APIRouter, Depends

from ..._meta import __version__, api_version, api_vtag
from ...models.schemas.meta import Meta
from ..dependencies.application import get_reverse_url_mapper

router = APIRouter()


@router.get("", response_model=Meta)
async def get_service_metadata(
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    return Meta(
        name=__name__.split(".")[0],
        version=api_version,
        released={api_vtag: api_version},
        docs_url=url_for("redoc_html"),
        docs_dev_url=url_for("swagger_ui_html"),
    )
