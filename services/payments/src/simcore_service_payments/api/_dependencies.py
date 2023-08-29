import logging
import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from servicelib.fastapi.dependencies import get_app, get_reverse_url_mapper

from ..core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


#
# DEPENDENCIES
#


def get_settings(request: Request) -> ApplicationSettings:
    app_settings: ApplicationSettings = request.app.state.settings
    assert app_settings  # nosec
    return app_settings


_get_basic_credentials = HTTPBasic()


def get_validated_credentials(
    credentials: HTTPBasicCredentials | None = Depends(_get_basic_credentials),
    settings: ApplicationSettings = Depends(get_settings),
) -> HTTPBasicCredentials:
    def _is_valid(current: str, expected: str) -> bool:
        return secrets.compare_digest(current.encode("utf8"), expected.encode("utf8"))

    if not credentials or not (
        _is_valid(
            credentials.username,
            expected=settings.PAYMENTS_USERNAME,
        )
        and _is_valid(
            credentials.password,
            expected=settings.PAYMENTS_PASSWORD.get_secret_value(),
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials


assert get_reverse_url_mapper  # nosec
assert get_app  # nosec


__all__: tuple[str, ...] = (
    "get_reverse_url_mapper",
    "get_app",
)
