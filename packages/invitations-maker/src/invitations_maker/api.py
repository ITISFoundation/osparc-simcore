from datetime import datetime
from typing import Any, Callable

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import PlainTextResponse
from pydantic import AnyHttpUrl, BaseModel

from ._meta import API_VERSION, API_VTAG

router = APIRouter()


def get_reverse_url_mapper(request: Request) -> Callable:
    def reverse_url_mapper(name: str, **path_params: Any) -> str:
        return request.url_for(name, **path_params)

    return reverse_url_mapper


def get_settings(request: Request) -> ApplicationSettings:
    return request.app.state.settings


def get_app(request: Request) -> FastAPI:
    return request.app


@router.get("/", include_in_schema=False, response_class=PlainTextResponse)
async def check_service_health():
    return f"{__name__}@{datetime.utcnow().isoformat()}"


#
# SCHEMA
#


class Meta(BaseModel):
    name: str
    version: str
    docs_url: AnyHttpUrl = "https://docs.osparc.io"
    docs_dev_url: AnyHttpUrl = "https://api.osparc.io/dev/docs"


@router.get("/meta", response_model=Meta)
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
