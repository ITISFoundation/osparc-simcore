import logging
import base64
from cryptography import fernet

from aiohttp_session import setup as _setup_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage

__all__ = ['setup_session']

_LOGGER = logging.getLogger(__file__)


def setup_session(app):
    _LOGGER.debug("Setting up ... ")

    secret_key = app['config'].get("SECRET_KEY")
    if secret_key is None:
        # secret_key must be 32 url-safe base64-encoded bytes
        fernet_key = fernet.Fernet.generate_key()
        secret_key = base64.urlsafe_b64decode(fernet_key)
        app['config']['SECRET_KEY'] = secret_key

    storage = EncryptedCookieStorage(secret_key, cookie_name='API_SESSION')
    _setup_session(app, storage)
