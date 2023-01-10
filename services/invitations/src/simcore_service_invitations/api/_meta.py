import logging
from datetime import datetime
from typing import Callable

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, HttpUrl

from .._meta import API_VERSION, PROJECT_NAME
from ._dependencies import get_reverse_url_mapper

logger = logging.getLogger(__name__)


#
# API SCHEMA MODELS
#

INVALID_INVITATION_URL_MSG = "Invalid invitation link"


class Meta(BaseModel):
    name: str
    version: str
    docs_url: HttpUrl


#
# ROUTE HANDLERS
#
router = APIRouter()


@router.get("/", response_class=PlainTextResponse)
async def healthcheck():
    return f"{__name__}@{datetime.utcnow().isoformat()}"


@router.get("/meta", response_model=Meta)
async def get_service_metadata(
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    return Meta(
        name=PROJECT_NAME,
        version=API_VERSION,
        docs_url=url_for("swagger_ui_html"),
    )
