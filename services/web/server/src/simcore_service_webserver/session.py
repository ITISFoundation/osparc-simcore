""" user's session plugin

"""
import base64
import logging
from typing import Union

import aiohttp_session
from aiohttp import web
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography import fernet
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .session_settings import SessionSettings, get_plugin_settings

logger = logging.getLogger(__name__)


def generate_fernet_secret_key() -> bytes:
    # secret_key must be 32 url-safe base64-encoded bytes
    fernet_key = fernet.Fernet.generate_key()
    secret_key = base64.urlsafe_b64decode(fernet_key)
    return secret_key


def _setup_encrypted_cookie_sessions(
    *, app: web.Application, secret_key: Union[str, bytes]
):
    # EncryptedCookieStorage urlsafe_b64decode inside if passes bytes
    encrypted_cookie_sessions = EncryptedCookieStorage(
        secret_key=secret_key,
        cookie_name="osparc.WEBAPI_SESSION",
    )
    aiohttp_session.setup(app=app, storage=encrypted_cookie_sessions)


# alias
get_session = aiohttp_session.get_session


@app_module_setup(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_SESSION", logger=logger
)
def setup_session(app: web.Application):
    """
    Inits and registers a session middleware in aiohttp.web.Application

    - stores user-specific data into a session object
    - session object has a dict-like interface
    - installs middleware in ``aiohttp.web.Application`` that attaches to
    a session object to ``request``. Usage:
    ```
        async def my_handler(request)
            session = await get_session(request)
    ```
    - data sessions stored in encripted cookies.
        - client tx/rx session's data everytime (middleware?)
        - This way, we can scale in theory server-side w/o issues
    - based in aiotthp_session library : http://aiohttp-session.readthedocs.io/en/latest/

    """
    settings: SessionSettings = get_plugin_settings(app)

    _setup_encrypted_cookie_sessions(
        app=app, secret_key=settings.SESSION_SECRET_KEY.get_secret_value()
    )


__all__: tuple[str, ...] = (
    "generate_fernet_secret_key",
    "get_session",
    "setup_session",
)
