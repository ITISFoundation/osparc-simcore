import logging
import time

import aiohttp_session
from aiohttp import web
from aiohttp_session.cookie_storage import EncryptedCookieStorage

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
