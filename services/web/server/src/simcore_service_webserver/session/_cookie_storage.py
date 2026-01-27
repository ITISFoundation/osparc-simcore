"""
Extends aiohttp_session.cookie_storage

"""

import logging
import time

import aiohttp_session
from aiohttp import web
from aiohttp_session.cookie_storage import EncryptedCookieStorage

from .errors import SessionValueError

_logger = logging.getLogger(__name__)


def _share_cookie_across_all_subdomains(
    request: web.BaseRequest, params: aiohttp_session._CookieParams
) -> aiohttp_session._CookieParams:
    """
    Shares cookie across all subdomains, by appending a dot (`.`) in front of the domain name
    overwrite domain from `None` (browser sets `example.com`) to `.example.com`
    """
    host = request.url.host
    if host is None:
        raise SessionValueError(invalid="host", host=host, request_url=request.url, params=params)

    params["domain"] = f".{host.lstrip('.')}"

    return params


class SharedCookieEncryptedCookieStorage(EncryptedCookieStorage):
    async def save_session(
        self,
        request: web.Request,
        response: web.StreamResponse,
        session: aiohttp_session.Session,
    ) -> None:
        # link response to originating request (allows to detect the original request url)
        response._req = request  # pylint:disable=protected-access  # noqa: SLF001

        await super().save_session(request, response, session)

    def save_cookie(
        self,
        response: web.StreamResponse,
        cookie_data: str,
        *,
        max_age: int | None = None,
    ) -> None:
        params = self._cookie_params.copy()
        request = response._req  # pylint:disable=protected-access  # noqa: SLF001
        if not request:
            raise SessionValueError(
                invalid="request",
                invalid_request=request,
                response=response,
                params=params,
            )

        params = _share_cookie_across_all_subdomains(request, params)

        # --------------------------------------------------------
        # WARNING: the code below is taken and adapted from the superclass
        # implementation `EncryptedCookieStorage.save_cookie`
        # Adjust in case the base library changes.
        assert aiohttp_session.__version__ == "2.11.0"  # nosec
        # --------------------------------------------------------

        if max_age is not None:
            params["max_age"] = max_age
            t = time.gmtime(time.time() + max_age)
            params["expires"] = time.strftime("%a, %d-%b-%Y %T GMT", t)

        if not cookie_data:
            response.del_cookie(
                self._cookie_name,
                domain=params.get("domain"),
                path=params.get("path", "/"),
            )
        else:
            response.set_cookie(self._cookie_name, cookie_data, **params)
