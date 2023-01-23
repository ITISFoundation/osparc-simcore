import logging
import secrets
from typing import Any, Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from ..core.settings import ApplicationSettings

logger = logging.getLogger(__name__)


#
# DEPENDENCIES
#


def get_reverse_url_mapper(request: Request) -> Callable:
    def _reverse_url_mapper(name: str, **path_params: Any) -> str:
        url: str = request.url_for(name, **path_params)
        return url

    return _reverse_url_mapper


def get_settings(request: Request) -> ApplicationSettings:
    app_settings: ApplicationSettings = request.app.state.settings
    assert app_settings  # nosec
    return app_settings


_get_basic_credentials = HTTPBasic()  # NOTE: adds Auth specs in openapi.json


def get_validated_credentials(
    credentials: Optional[HTTPBasicCredentials] = Depends(_get_basic_credentials),
    settings: ApplicationSettings = Depends(get_settings),
) -> Optional[HTTPBasicCredentials]:

    if settings.is_auth_enabled:

        def _is_valid(current: str, expected: str) -> bool:
            return secrets.compare_digest(
                current.encode("utf8"), expected.encode("utf8")
            )

        if (
            not credentials
            or not _is_valid(
                credentials.username,
                expected=settings.INVITATIONS_USERNAME,
            )
            or not _is_valid(
                credentials.password,
                expected=settings.INVITATIONS_PASSWORD.get_secret_value(),
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Basic"},
            )
    else:
        assert not settings.is_auth_enabled  # nosec

        logger.debug("Auth was disabled: %s", f"{settings=}")

    return credentials
