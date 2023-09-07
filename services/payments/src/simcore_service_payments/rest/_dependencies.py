import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, OAuth2PasswordBearer, OAuth2PasswordRequestForm
from servicelib.fastapi.dependencies import get_app, get_reverse_url_mapper
from servicelib.utils_secrets import compare_secrets

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


def get_validated_form_data(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    settings: Annotated[ApplicationSettings, Depends(get_settings)],
) -> OAuth2PasswordRequestForm:

    if not form_data or not (
        compare_secrets(
            form_data.username + form_data.password,
            expected=settings.PAYMENTS_USERNAME
            + settings.PAYMENTS_PASSWORD.get_secret_value(),
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username or password",
        )

    return form_data


# Implements `password` flow defined in OAuth2
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def raise_if_invalid_token(token: Annotated[str, Depends(_oauth2_scheme)]):
    # TODO: decode token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


assert get_reverse_url_mapper  # nosec
assert get_app  # nosec


__all__: tuple[str, ...] = (
    "get_app",
    "get_reverse_url_mapper",
    "get_validated_form_data",
)
