import json
import time
from typing import Dict, Optional

from cryptography.fernet import Fernet
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.requests import Request

from ...core.settings import AppSettings, WebServerSettings
from ...services.webserver import AuthSession
from .authentication import get_active_user_email

UNAVAILBLE_MSG = "backend service is disabled or unreachable"


def _get_app(request: Request) -> FastAPI:
    return request.app


def _get_settings(request: Request) -> WebServerSettings:
    app_settings: AppSettings = request.app.state.settings
    return app_settings.webserver


def _get_encrypt(request: Request) -> Optional[Fernet]:
    return getattr(request.app.state, "webserver_fernet", None)


def get_session_cookie(
    identity: str = Depends(get_active_user_email),
    settings: WebServerSettings = Depends(_get_settings),
    fernet: Optional[Fernet] = Depends(_get_encrypt),
) -> Dict:
    # Based on aiohttp_session and aiohttp_security
    # SEE services/web/server/tests/unit/with_dbs/test_login.py

    if fernet is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=UNAVAILBLE_MSG)

    # builds session cookie
    cookie_name = settings.session_name
    cookie_data = json.dumps(
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
    app: FastAPI = Depends(_get_app),
    session_cookies: Dict = Depends(get_session_cookie),
) -> AuthSession:
    """
        Lifetime of AuthSession wrapper is one request because it needs different session cookies
        Lifetime of embedded client is attached to the app lifetime
    """
    return AuthSession.create(app, session_cookies)
