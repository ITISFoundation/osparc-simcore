import logging
from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from servicelib.fastapi.dependencies import get_app, get_reverse_url_mapper

from ..._meta import API_VTAG
from ...core.settings import ApplicationSettings
from ...models.auth import SessionData
from ...services.auth import get_session_data
from ...services.resource_usage_tracker import ResourceUsageTrackerApi

_logger = logging.getLogger(__name__)


#
# core dependencies
#


def get_settings(request: Request) -> ApplicationSettings:
    app_settings: ApplicationSettings = request.app.state.settings
    assert app_settings  # nosec
    return app_settings


assert get_reverse_url_mapper  # nosec
assert get_app  # nosec

#
# services dependencies
#


def get_rut_api(request: Request) -> ResourceUsageTrackerApi:
    return cast(
        ResourceUsageTrackerApi, ResourceUsageTrackerApi.get_from_app_state(request.app)
    )


# Implements `password` flow defined in OAuth2
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"/{API_VTAG}/token")


async def get_current_session(
    settings: Annotated[ApplicationSettings, Depends(get_settings)],
    token: Annotated[str, Depends(_oauth2_scheme)],
) -> SessionData:
    return get_session_data(token, settings)


__all__: tuple[str, ...] = (
    "get_app",
    "get_reverse_url_mapper",
)
