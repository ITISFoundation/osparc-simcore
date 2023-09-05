import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends

from .._meta import API_VERSION, PROJECT_NAME
from ..models.schemas.meta import Meta
from ._dependencies import get_reverse_url_mapper

_logger = logging.getLogger(__name__)


#
# ROUTE HANDLERS
#
router = APIRouter()


@router.get("/meta", response_model=Meta)
async def get_service_metadata(
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):
    return Meta(
        name=PROJECT_NAME,
        version=API_VERSION,
        docs_url=url_for("swagger_ui_html"),
    )
