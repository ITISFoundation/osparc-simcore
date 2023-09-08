import logging
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from ..core.settings import ApplicationSettings
from ..services.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    authenticate_user,
    encode_access_token,
)
from ._dependencies import get_settings

_logger = logging.getLogger(__name__)


router = APIRouter()


class Token(BaseModel):
    access_token: str
    token_type: str


@router.post("/token", response_model=Token)
async def login_to_create_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    settings: Annotated[ApplicationSettings, Depends(get_settings)],
):
    if not authenticate_user(form_data.username, form_data.password, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "access_token": encode_access_token(
            username=form_data.username,
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        ),
        "token_type": "bearer",
    }
