import logging
import secrets
from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from ..core.settings import WebApplicationSettings

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


def get_current_username(
    credentials: HTTPBasicCredentials = Depends(get_basic_credentials),
    settings: WebApplicationSettings = Depends(get_settings),
) -> str:
    def _is_valid(current: str, expected: str) -> bool:
        return secrets.compare_digest(current.encode("utf8"), expected.encode("utf8"))

    if not (
        _is_valid(
            credentials.username,
            expected=settings.INVITATIONS_USERNAME,
        )
        and _is_valid(
            credentials.password,
            expected=settings.INVITATIONS_PASSWORD,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    assert isinstance(credentials.username, str)  # nosec
    return credentials.username
