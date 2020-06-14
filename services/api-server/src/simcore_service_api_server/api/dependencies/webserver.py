import base64
import json
import time
from typing import Dict

from cryptography import fernet
from fastapi import Depends
from fastapi.requests import Request

from ...core.settings import AppSettings, WebServerSettings
from .authentication import get_active_user_email


def _get_settings(request: Request) -> WebServerSettings:
    app_settings: AppSettings = request.app.state.settings
    return app_settings.webserver


def create_session_cookie(
    identity: str = Depends(get_active_user_email),
    settings: WebServerSettings = Depends(_get_settings),
) -> Dict:
    # Based on aiohttp_session and aiohttp_security
    # SEE services/web/server/tests/unit/with_dbs/test_login.py

    # normalize
    secret_key_bytes = settings.session_secret_key.get_secret_value().encode("utf-8")
    while len(secret_key_bytes) < 32:
        secret_key_bytes += secret_key_bytes
    secret_key = secret_key_bytes[:32]

    if isinstance(secret_key, str):
        pass
    elif isinstance(secret_key, (bytes, bytearray)):
        secret_key = base64.urlsafe_b64encode(secret_key)

    # encrypt
    _fernet = fernet.Fernet(secret_key)

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
    encrypted_cookie_data = _fernet.encrypt(cookie_data).decode("utf-8")

    return {cookie_name: encrypted_cookie_data}


async def get_webserver_client(_settings: WebServerSettings = Depends(_get_settings)):
    # create session
    # settings.host, settings.port
    pass
