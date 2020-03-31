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

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup

from .session_config import CONFIG_SECTION_NAME

logger = logging.getLogger(__file__)


def generate_key():
    # secret_key must be 32 url-safe base64-encoded bytes
    fernet_key = fernet.Fernet.generate_key()
    secret_key = base64.urlsafe_b64decode(fernet_key)
    return secret_key


@app_module_setup(__name__, ModuleCategory.ADDON, logger=logger)
def setup_session(app: web.Application):
    """
        Inits and registers a session middleware in aiohttp.web.Application
    """
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

    # secret key needed by EncryptedCookieStorage: is *bytes* key with length of *32*
    secret_key_bytes = cfg["secret_key"].encode("utf-8")
    if len(secret_key_bytes) == 0:
        raise ValueError("Empty %s.secret_key in config. Expected at least length 32")

    while len(secret_key_bytes) < 32:
        secret_key_bytes += secret_key_bytes

    # EncryptedCookieStorage urlsafe_b64decode inside if passes bytes
    storage = EncryptedCookieStorage(
        secret_key=secret_key_bytes[:32], cookie_name="API_SESSION"
    )

    aiohttp_session.setup(app, storage)


# alias
get_session = aiohttp_session.get_session


__all__ = ("setup_session", "get_session")
