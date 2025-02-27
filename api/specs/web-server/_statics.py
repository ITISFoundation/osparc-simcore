# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from simcore_service_webserver.constants import INDEX_RESOURCE_NAME
from simcore_service_webserver.statics.settings import FrontEndInfoDict

router = APIRouter(
    tags=["statics"],
)


@router.get("/", response_class=HTMLResponse)
async def get_cached_frontend_index():
    ...


assert get_cached_frontend_index.__name__ == INDEX_RESOURCE_NAME


class StaticFrontEndDict(FrontEndInfoDict, total=False):
    issues: Any
    vendor: Any
    manuals: Any


@router.get("/static-frontend-data.json", response_model=StaticFrontEndDict)
async def static_frontend_data():
    """Generic static info on the product's app"""
