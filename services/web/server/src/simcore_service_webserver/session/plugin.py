""" user's session plugin

"""

import logging
import time

import aiohttp_session
from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from settings_library.utils_session import DEFAULT_SESSION_COOKIE_NAME

from ._cookie_storage import SharedCookieEncryptedCookieStorage
from .settings import SessionSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


def _share_cookie_across_all_subdomains(
    response: web.StreamResponse, params: aiohttp_session._CookieParams
) -> aiohttp_session._CookieParams:
    # share cookie across all subdomains, by appending a dot (`.`) in front of the domain name
    # overwrite domain from `None` (browser sets `example.com`) to `.example.com`
    request = response._req  # pylint:disable=protected-access  # noqa: SLF001
    assert isinstance(request, web.Request)  # nosec
    params["domain"] = f".{request.url.host}"
    return params


class SharedCookieEncryptedCookieStorage(EncryptedCookieStorage):
    async def save_session(
        self,
        request: web.Request,
        response: web.StreamResponse,
        session: aiohttp_session.Session,
    ) -> None:
        # link response to originating request (allows to detect the orginal request url)
        response._req = request  # pylint:disable=protected-access  # noqa: SLF001

        await super().save_session(request, response, session)

    def save_cookie(
        self,
        response: web.StreamResponse,
        cookie_data: str,
        *,
        max_age: int | None = None,
    ) -> None:
        # NOTE: WARNING: the only difference between the superclass and this implementation
        # is the statement below where the domain name is set. Adjust in case the base library changes.
        params = _share_cookie_across_all_subdomains(
            response, self._cookie_params.copy()
        )

        if max_age is not None:
            params["max_age"] = max_age
            t = time.gmtime(time.time() + max_age)
            params["expires"] = time.strftime("%a, %d-%b-%Y %T GMT", t)
        if not cookie_data:

            response.del_cookie(
                self._cookie_name, domain=params["domain"], path=params["path"]
            )
        else:
            response.set_cookie(self._cookie_name, cookie_data, **params)


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
    app.middlewares[-1].__middleware_name__ = f"{__name__}.session"  # type: ignore[union-attr] # PC this attribute does not exist and mypy does not like it
