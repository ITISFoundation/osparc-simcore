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
