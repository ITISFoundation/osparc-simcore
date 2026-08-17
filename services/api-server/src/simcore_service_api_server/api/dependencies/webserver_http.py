import time
from typing import Annotated

from common_library.gettext_support import SupportedLocale
from common_library.json_serialization import json_dumps
from cryptography.fernet import Fernet
from fastapi import Depends, FastAPI, HTTPException, Request, status

from ..._constants import MSG_BACKEND_SERVICE_UNAVAILABLE
from ...core.settings import ApplicationSettings, WebServerSettings
from ...services_http.webserver import AuthSession
from .application import get_app, get_settings
from .authentication import (
    Identity,
    get_active_user_email,
    get_current_identity,
)


def _get_settings(
    app_settings: Annotated[ApplicationSettings, Depends(get_settings)],
) -> WebServerSettings:
    settings = app_settings.API_SERVER_WEBSERVER
    if not settings:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=MSG_BACKEND_SERVICE_UNAVAILABLE)
    assert isinstance(settings, WebServerSettings)  # nosec
    return settings


def get_session_cookie(
    identity: Annotated[str, Depends(get_active_user_email)],
    settings: Annotated[WebServerSettings, Depends(_get_settings)],
    app: Annotated[FastAPI, Depends(get_app)],
) -> dict:
    # Based on aiohttp_session and aiohttp_security
    # SEE services/web/server/tests/unit/with_dbs/test_login.py

    fernet: Fernet | None = getattr(app.state, "webserver_fernet", None)

    if fernet is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=MSG_BACKEND_SERVICE_UNAVAILABLE)

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


def _get_request_locale(request: Request) -> SupportedLocale | None:
    # NOTE: `Request` is auto-injected by FastAPI's dependency resolution
    # (any dependency, not only path operations, can declare it). Wrapping it
    # in this dedicated sub-dependency (rather than adding `request: Request`
    # directly to `get_webserver_session`) keeps `get_webserver_session`
    # callable outside an HTTP request context (e.g. from Celery workers,
    # see `modules/celery/worker/_functions_tasks.py`), where `locale` simply
    # defaults to `None`.
    return getattr(request.state, "locale", None)


def get_webserver_session(
    app: Annotated[FastAPI, Depends(get_app)],
    session_cookies: Annotated[dict, Depends(get_session_cookie)],
    identity: Annotated[Identity, Depends(get_current_identity)],
    locale: Annotated[SupportedLocale | None, Depends(_get_request_locale)] = None,
) -> AuthSession:
    """
    Lifetime of AuthSession wrapper is one request because it needs different session cookies
    Lifetime of embedded client is attached to the app lifetime
    """
    session = AuthSession.create(
        app,
        session_cookies=session_cookies,
        product_name=identity.product_name,
        user_id=identity.user_id,
        locale=locale,
    )
    assert isinstance(session, AuthSession)  # nosec
    return session


__all__: tuple[str, ...] = ("AuthSession",)
