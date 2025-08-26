"""user's session plugin"""

import logging

import aiohttp_session
from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from settings_library.utils_session import DEFAULT_SESSION_COOKIE_NAME

from ._cookie_storage import SharedCookieEncryptedCookieStorage
from .settings import SessionSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_SESSION", logger=_logger
)
def setup_session(app: web.Application):
    """
    Inits and registers a session middleware in aiohttp.web.Application


    - based in aiotthp_session library : http://aiohttp-session.readthedocs.io/en/latest/

    """
    settings: SessionSettings = get_plugin_settings(app)

    # - Sessions stored in encrypted cookies (EncryptedCookieStorage)
    #   - client tx/rx session's data everytime (middleware?)
    #   - This way, we can scale in theory server-side w/o issues
    #

    # SEE https://aiohttp-session.readthedocs.io/en/latest/reference.html#abstract-storage
    encrypted_cookie_sessions = SharedCookieEncryptedCookieStorage(
        secret_key=settings.SESSION_SECRET_KEY.get_secret_value(),
        cookie_name=DEFAULT_SESSION_COOKIE_NAME,
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        max_age=settings.SESSION_COOKIE_MAX_AGE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )
    aiohttp_session.setup(app=app, storage=encrypted_cookie_sessions)
    setattr(  # noqa: B010
        # aiohttp_session.setup has appended a middleware. We add an identifier (mostly for debugging)
        app.middlewares[-1],
        "__middleware_name__",
        f"{__name__}.session",
    )
