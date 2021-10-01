from typing import Callable

from fastapi import APIRouter, Depends

from ..._meta import API_VERSION, API_VTAG, __version__
from ...models.schemas.meta import Meta
from ..dependencies.application import get_reverse_url_mapper

router = APIRouter()


@router.get("", response_model=Meta)
async def get_service_metadata(
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    return Meta(
        name=__name__.split(".")[0],
        version=API_VERSION,
        released={API_VTAG: API_VERSION},
        docs_url=url_for("redoc_html"),
        docs_dev_url=url_for("swagger_ui_html"),
    )
