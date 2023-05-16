import logging
from typing import Callable

from fastapi import APIRouter, Depends
from pydantic import BaseModel, HttpUrl

from .._meta import API_VERSION, PROJECT_NAME
from ._dependencies import get_reverse_url_mapper

logger = logging.getLogger(__name__)


#
# API SCHEMA MODELS
#

INVALID_INVITATION_URL_MSG = "Invalid invitation link"


class _Meta(BaseModel):
    name: str
    version: str
    docs_url: HttpUrl


#
# ROUTE HANDLERS
#
router = APIRouter()


@router.get("/meta", response_model=_Meta)
async def get_service_metadata(
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    return _Meta(
        name=PROJECT_NAME,
        version=API_VERSION,
        docs_url=url_for("swagger_ui_html"),
    )
