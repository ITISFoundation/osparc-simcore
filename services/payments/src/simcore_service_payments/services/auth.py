from datetime import timedelta

import arrow
from fastapi import HTTPException, status
from jose import JWTError, jwt
from pydantic import BaseModel
from servicelib.utils_secrets import compare_secrets

from ..core.settings import ApplicationSettings


def authenticate_user(username: str, password: str, settings: ApplicationSettings):
    return compare_secrets(
        username + password,
        expected=settings.PAYMENTS_USERNAME
        + settings.PAYMENTS_PASSWORD.get_secret_value(),
    )


#
# JW Tokens
#

# to get a string like this run: openssl rand -hex 32
ALGORITHM = "HS256"


_credencial_exception_kwargs = {
    "status_code": status.HTTP_401_UNAUTHORIZED,
    "detail": "Invalid authentication credentials",
    "headers": {"WWW-Authenticate": "Bearer"},
}


def encode_access_token(username: str, settings: ApplicationSettings) -> str:
    expire = arrow.utcnow().datetime + timedelta(
        minutes=settings.PAYMENTS_ACCESS_TOKEN_EXPIRE_MINUTES
    )

    # SEE https://jwt.io/introduction/
    claims = {
        # Registered claims
        "sub": username,  # https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.2
        "exp": expire,  # https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.4
    }
    return jwt.encode(
        claims,
        key=settings.PAYMENTS_ACCESS_TOKEN_SECRET_KEY.get_secret_value(),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str, settings: ApplicationSettings) -> str | None:
    """
    Raises:
        JWTError
    """
    claims = jwt.decode(
        token,
        settings.PAYMENTS_ACCESS_TOKEN_SECRET_KEY.get_secret_value(),
        algorithms=[ALGORITHM],
    )
    username: str | None = claims.get("sub", None)
    return username


class SessionData(BaseModel):
    username: str | None = None


def get_session_data(token: str, settings: ApplicationSettings) -> SessionData:
    """
    Raises:
        HTTPException: 401
    """

    try:
        username = decode_access_token(token, settings)
    except JWTError as err:
        raise HTTPException(**_credencial_exception_kwargs) from err

    if username is None:
        raise HTTPException(**_credencial_exception_kwargs)

    return SessionData(username=username)
