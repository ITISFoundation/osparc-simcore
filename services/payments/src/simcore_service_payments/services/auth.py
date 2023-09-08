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
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


_credencial_exception_kwargs = {
    "status_code": status.HTTP_401_UNAUTHORIZED,
    "detail": "Invalid authentication credentials",
    "headers": {"WWW-Authenticate": "Bearer"},
}


def encode_access_token(username: str, expires_delta: timedelta) -> str:
    # SEE https://jwt.io/introduction/
    expire = arrow.utcnow().datetime + expires_delta
    claims = {
        # Registered claims
        "sub": username,  # https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.2
        "exp": expire,  # https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.4
    }
    return jwt.encode(claims, key=SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """
    Raises:
        JWTError
    """
    claims = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    username: str | None = claims.get("sub", None)
    return username


class SessionData(BaseModel):
    username: str | None = None


def get_session_data(token: str) -> SessionData:

    """
    Raises:
        HTTPException: 401

    Returns:
        _description_
    """

    try:
        username = decode_access_token(token)
    except JWTError as err:
        raise HTTPException(**_credencial_exception_kwargs) from err

    if username is None:
        raise HTTPException(**_credencial_exception_kwargs)

    return SessionData(username=username)
