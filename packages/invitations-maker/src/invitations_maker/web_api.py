from datetime import datetime
from typing import Any, Callable

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import PlainTextResponse
from pydantic import AnyHttpUrl, BaseModel, Field

from ._meta import API_VERSION, PROJECT_NAME
from .invitations import InvitationData, create_invitation_link
from .settings import ApplicationSettings

#
# DEPENDENCIES
#


def get_reverse_url_mapper(request: Request) -> Callable:
    def reverse_url_mapper(name: str, **path_params: Any) -> str:
        return request.url_for(name, **path_params)

    return reverse_url_mapper


def get_settings(request: Request) -> ApplicationSettings:
    return request.app.state.settings


def get_app(request: Request) -> FastAPI:
    return request.app


#
# SCHEMA MODELS
#


class Meta(BaseModel):
    name: str
    version: str
    docs_url: AnyHttpUrl


class Invitation(InvitationData):
    url: AnyHttpUrl = Field(..., description="Invitation link")


#
# ROUTE HANDLERS
#
router = APIRouter()


@router.get("/", response_class=PlainTextResponse)
async def check_service_health():
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


@router.post("/invite", response_model=Invitation, response_model_by_alias=False)
async def generate_invitation(
    invitation_data: InvitationData,
    settings: ApplicationSettings = Depends(get_settings),
):
    invitation_link = create_invitation_link(
        invitation_data,
        secret_key=settings.INVITATIONS_MAKER_SECRET_KEY.get_secret_value(),
        base_url=settings.INVITATIONS_MAKER_OSPARC_URL,
    )

    return Invitation(url=invitation_link, **invitation_data.dict())
