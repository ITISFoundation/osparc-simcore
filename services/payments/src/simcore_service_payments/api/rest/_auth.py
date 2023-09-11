import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from ...core.settings import ApplicationSettings
from ...models.schemas.auth import Token
from ...services.auth import authenticate_user, encode_access_token
from ._dependencies import get_settings

_logger = logging.getLogger(__name__)


router = APIRouter()


@router.post("/token", response_model=Token)
async def login_to_create_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    settings: Annotated[ApplicationSettings, Depends(get_settings)],
):
    #
    # OAuth2PasswordRequestForm: OAuth2 specifies that when using the "password flow"
    # the client must send a username and password fields as form data
    #
    if not authenticate_user(form_data.username, form_data.password, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "access_token": encode_access_token(
            username=form_data.username, settings=settings
        ),
        "token_type": "bearer",
    }
