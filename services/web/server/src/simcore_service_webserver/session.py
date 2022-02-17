""" user's session submodule

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
        - TODO: test and demo statement above
    - based in aiotthp_session library : http://aiohttp-session.readthedocs.io/en/latest/

    TODO: check storing JSON-ed data into redis-service, keeping into cookie only redis key (random UUID). Pros/cons analysis.
"""
import base64
import logging

import aiohttp_session
from aiohttp import web
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography import fernet
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .session_settings import SessionSettings, get_plugin_settings

logger = logging.getLogger(__file__)


def generate_key():
    # secret_key must be 32 url-safe base64-encoded bytes
    fernet_key = fernet.Fernet.generate_key()
    secret_key = base64.urlsafe_b64decode(fernet_key)
    return secret_key


@app_module_setup(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_SESSION", logger=logger
)
def setup_session(app: web.Application):
    """
    Inits and registers a session middleware in aiohttp.web.Application
    """
    settings: SessionSettings = get_plugin_settings(app)

    # EncryptedCookieStorage urlsafe_b64decode inside if passes bytes
    storage = EncryptedCookieStorage(
        secret_key=settings.SESSION_SECRET_KEY.get_secret_value(),
        cookie_name="osparc.WEBAPI_SESSION",
    )

    aiohttp_session.setup(app, storage)


# alias
get_session = aiohttp_session.get_session


__all__ = ("setup_session", "get_session")
