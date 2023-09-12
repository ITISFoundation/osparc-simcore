"""
Implements OAuth2 with Password and Bearer (w/ JWT tokens)

"""

from datetime import timedelta

import arrow
from fastapi import HTTPException, status
from jose import JWTError, jwt
from servicelib.utils_secrets import are_secrets_equal

from ..core.settings import ApplicationSettings
from ..models.auth import SessionData


def authenticate_user(username: str, password: str, settings: ApplicationSettings):
    return are_secrets_equal(
        username + password,
        expected=settings.PAYMENTS_USERNAME
        + settings.PAYMENTS_PASSWORD.get_secret_value(),
    )


#
# JSON Web Tokens (https://jwt.io/introduction/)
#


_ALGORITHM = "HS256"


def encode_access_token(username: str, settings: ApplicationSettings) -> str:
    expire = arrow.utcnow().datetime + timedelta(
        minutes=settings.PAYMENTS_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    # SEE https://jwt.io/introduction/
    payload_claims = {
        # Registered claims
        "sub": username,  # subject: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.2
        "exp": expire,  # expiration date: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.4
    }
    json_web_token: str = jwt.encode(
        payload_claims,
        key=settings.PAYMENTS_ACCESS_TOKEN_SECRET_KEY.get_secret_value(),
        algorithm=_ALGORITHM,
    )
    return json_web_token


def decode_access_token(token: str, settings: ApplicationSettings) -> str | None:
    """
    Raises:
        JWTError: If the signature is invalid in any way.
          - ExpiredSignatureError(JWTError): If the signature has expired.
          - JWTClaimsError(JWTError): If any claim is invalid in any way.
    """
    claims = jwt.decode(
        token,
        settings.PAYMENTS_ACCESS_TOKEN_SECRET_KEY.get_secret_value(),
        algorithms=[_ALGORITHM],
    )
    username: str | None = claims.get("sub", None)
    return username


_credencial_401_unauthorized_exception_kwargs = {
    "status_code": status.HTTP_401_UNAUTHORIZED,
    "detail": "Invalid authentication credentials",
    "headers": {"WWW-Authenticate": "Bearer"},
}


def get_session_data(token: str, settings: ApplicationSettings) -> SessionData:
    """
    Raises:
        HTTPException: 401
    """

    try:
        username = decode_access_token(token, settings)
    except JWTError as err:
        raise HTTPException(**_credencial_401_unauthorized_exception_kwargs) from err

    if username is None:
        raise HTTPException(**_credencial_401_unauthorized_exception_kwargs)

    return SessionData(username=username)
