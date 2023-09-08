import logging
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from servicelib.fastapi.dependencies import get_app, get_reverse_url_mapper

from ..core.settings import ApplicationSettings
from ..services.auth import SessionData, get_session_data

_logger = logging.getLogger(__name__)


#
# DEPENDENCIES
#


def get_settings(request: Request) -> ApplicationSettings:
    app_settings: ApplicationSettings = request.app.state.settings
    assert app_settings  # nosec
    return app_settings


assert get_reverse_url_mapper  # nosec
assert get_app  # nosec


# Implements `password` flow defined in OAuth2
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_session(
    token: Annotated[str, Depends(_oauth2_scheme)]
) -> SessionData:
    session = get_session_data(token)

    return session


__all__: tuple[str, ...] = (
    "get_app",
    "get_reverse_url_mapper",
)
