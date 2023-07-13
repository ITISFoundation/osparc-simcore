from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends

from ..._meta import API_VERSION, API_VTAG
from ...models.schemas.meta import Meta
from ..dependencies.application import get_reverse_url_mapper

router = APIRouter()


@router.get("", response_model=Meta)
async def get_service_metadata(
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):
    return Meta(
        name=__name__.split(".")[0],
        version=API_VERSION,  # type: ignore
        released={API_VTAG: API_VERSION},  # type: ignore
        docs_url=url_for("swagger_ui_html"),
        docs_dev_url=url_for("swagger_ui_html"),
    )
