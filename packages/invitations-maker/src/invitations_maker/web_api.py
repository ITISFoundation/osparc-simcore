import logging
import secrets
from datetime import datetime
from typing import Any, Callable
from urllib import parse

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import AnyHttpUrl, BaseModel, Field
from starlette.datastructures import URL

from ._meta import API_VERSION, PROJECT_NAME
from .invitations import InvitationData, create_invitation_link, decrypt_invitation
from .settings import WebApplicationSettings

logger = logging.getLogger(__name__)


#
# DEPENDENCIES
#
get_basic_credentials = HTTPBasic()


def get_reverse_url_mapper(request: Request) -> Callable:
    def _reverse_url_mapper(name: str, **path_params: Any) -> str:
        url: str = request.url_for(name, **path_params)
        return url

    return _reverse_url_mapper


def get_settings(request: Request) -> WebApplicationSettings:
    app_settings: WebApplicationSettings = request.app.state.settings
    assert app_settings  # nosec
    return app_settings


def get_app(request: Request) -> FastAPI:
    return request.app


def get_current_username(
    credentials: HTTPBasicCredentials = Depends(get_basic_credentials),
    settings: WebApplicationSettings = Depends(get_settings),
) -> str:

    # username
    current: bytes = credentials.username.encode("utf8")
    expected: bytes = settings.INVITATIONS_USERNAME.encode("utf8")
    is_correct_username = secrets.compare_digest(current, expected)

    # password
    current = credentials.password.encode("utf8")
    expected = settings.INVITATIONS_PASSWORD.get_secret_value().encode("utf8")
    is_correct_password = secrets.compare_digest(current, expected)

    # check
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    assert isinstance(credentials.username, str)  # nosec
    return credentials.username


#
# API SCHEMA MODELS
#


class Meta(BaseModel):
    name: str
    version: str
    docs_url: AnyHttpUrl


class InvitationCreate(InvitationData):
    class Config:
        # Same as InvitationData but WITHOUT alias
        schema_extra = {
            "example": {
                "issuer": "issuerid",
                "guest": "invitedguest@company.com",
                "trial_account_days": None,
            }
        }


class InvitationGet(InvitationCreate):
    invitation_url: AnyHttpUrl = Field(..., description="Resulting invitation link")

    class Config:
        schema_extra = {
            "example": {
                "issuer": "issuerid",
                "guest": "invitedguest@company.com",
                "trial_account_days": None,
                "invitation_url": "https://foo.com/#/registration?invitation=1234",
            }
        }


class InvitationCheck(BaseModel):
    invitation_url: AnyHttpUrl = Field(..., description="Resulting invitation link")

    def get_invitation_code(self):
        try:

            query_params = dict(
                parse.parse_qsl(URL(self.invitation_url.fragment).query)
            )
            invitation_code = query_params["invitation"]
            return invitation_code

        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid invitation_url",
            )


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


@router.post("/invitation", response_model=InvitationGet, response_model_by_alias=False)
async def create_invitation(
    invitation_create: InvitationCreate,
    settings: WebApplicationSettings = Depends(get_settings),
    username: str = Depends(get_current_username),
):
    """Generates a new invitation link"""
    assert username == settings.INVITATIONS_USERNAME  # nosec

    invitation_link = create_invitation_link(
        invitation_create,
        secret_key=settings.INVITATIONS_MAKER_SECRET_KEY.get_secret_value().encode(),
        base_url=settings.INVITATIONS_MAKER_OSPARC_URL,
    )
    invitation = InvitationGet(
        invitation_url=invitation_link,
        **invitation_create.dict(),
    )

    logger.info("New invitation: %s", f"{invitation.json(indent=1)}")

    return invitation


@router.post(
    "/invitation:check", response_model=InvitationGet, response_model_by_alias=False
)
async def check_invitation(
    invitation_check: InvitationCheck,
    settings: WebApplicationSettings = Depends(get_settings),
    username: str = Depends(get_current_username),
):
    """Generates a new invitation link"""
    assert username == settings.INVITATIONS_USERNAME  # nosec

    invitation = decrypt_invitation(
        invitation_code=invitation_check.get_invitation_code(),
        secret_key=settings.INVITATIONS_MAKER_SECRET_KEY.get_secret_value().encode(),
    )

    invitation = InvitationGet(
        invitation_url=invitation_check.invitation_url,
        **invitation.dict(),
    )

    return invitation
