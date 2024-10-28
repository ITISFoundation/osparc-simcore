import time
from typing import Annotated

from common_library.json_serialization import json_dumps
from cryptography.fernet import Fernet
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.requests import Request
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER

from ..._constants import MSG_BACKEND_SERVICE_UNAVAILABLE
from ...core.settings import ApplicationSettings, WebServerSettings
from ...services.webserver import AuthSession
from .application import get_app, get_settings
from .authentication import Identity, get_active_user_email, get_current_identity


def _get_settings(
    app_settings: Annotated[ApplicationSettings, Depends(get_settings)],
) -> WebServerSettings:
    settings = app_settings.API_SERVER_WEBSERVER
    if not settings:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=MSG_BACKEND_SERVICE_UNAVAILABLE
        )
    assert isinstance(settings, WebServerSettings)  # nosec
    return settings


def _get_encrypt(request: Request) -> Fernet | None:
    e: Fernet | None = getattr(request.app.state, "webserver_fernet", None)
    return e


def get_session_cookie(
    identity: Annotated[str, Depends(get_active_user_email)],
    settings: Annotated[WebServerSettings, Depends(_get_settings)],
    fernet: Annotated[Fernet | None, Depends(_get_encrypt)],
) -> dict:
    # Based on aiohttp_session and aiohttp_security
    # SEE services/web/server/tests/unit/with_dbs/test_login.py

    if fernet is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=MSG_BACKEND_SERVICE_UNAVAILABLE
        )

    # builds session cookie
    cookie_name = settings.WEBSERVER_SESSION_NAME
    cookie_data = json_dumps(
        {
            "created": int(time.time()),  # now
            "session": {"AIOHTTP_SECURITY": identity},
            "path": "/",
            # extras? e.g. expiration
        }
    ).encode("utf-8")
    encrypted_cookie_data = fernet.encrypt(cookie_data).decode("utf-8")

    return {cookie_name: encrypted_cookie_data}


def get_webserver_session(
    app: Annotated[FastAPI, Depends(get_app)],
    session_cookies: Annotated[dict, Depends(get_session_cookie)],
    identity: Annotated[Identity, Depends(get_current_identity)],
) -> AuthSession:
    """
    Lifetime of AuthSession wrapper is one request because it needs different session cookies
    Lifetime of embedded client is attached to the app lifetime
    """
    product_header: dict[str, str] = {X_PRODUCT_NAME_HEADER: f"{identity.product_name}"}
    session = AuthSession.create(app, session_cookies, product_header)
    assert isinstance(session, AuthSession)  # nosec
    return session


__all__: tuple[str, ...] = (
    "AuthSession",
    "get_session_cookie",
    "get_webserver_session",
)
