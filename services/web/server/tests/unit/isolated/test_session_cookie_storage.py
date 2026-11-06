# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

import base64
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from http.cookies import Morsel, SimpleCookie
from typing import Final

from aiohttp import hdrs, web
from aiohttp.test_utils import make_mocked_request
from simcore_service_webserver.session._cookie_storage import (
    SharedCookieEncryptedCookieStorage,
)

_SESSION_SECRET_KEY: Final[str] = base64.urlsafe_b64encode(b"0" * 32).decode()
_SESSION_COOKIE_NAME: Final[str] = "osparc-sc2"


async def _parse_response_cookie(request: web.Request, response: web.StreamResponse) -> Morsel[str]:
    """Parses the Set-Cookie header the response sends, with a parser independent of the library"""
    await response.prepare(request)  # aiohttp writes cookies into the headers only when preparing

    headers = response.headers.getall(hdrs.SET_COOKIE, [])
    assert len(headers) == 1, headers

    cookie: SimpleCookie = SimpleCookie()
    cookie.load(headers[0])
    assert list(cookie) == [_SESSION_COOKIE_NAME], headers[0]
    return cookie[_SESSION_COOKIE_NAME]


async def test_session_cookie_is_shared_with_all_subdomains_of_the_request_host():
    storage = SharedCookieEncryptedCookieStorage(
        secret_key=_SESSION_SECRET_KEY,
        cookie_name=_SESSION_COOKIE_NAME,
    )
    session = await storage.new_session()
    session["AIOHTTP_SECURITY"] = "me@example.com"

    request = make_mocked_request("GET", "/", headers={"Host": "osparc.example.com"})
    response = web.StreamResponse()

    await storage.save_session(request, response, session)

    # RFC 6265 section 5.1.3: a cookie stored for ".example.com" is also sent to
    # any subdomain, which is what lets vendor services authenticate
    cookie = await _parse_response_cookie(request, response)
    assert cookie["domain"] == ".osparc.example.com"


async def test_session_cookie_carries_max_age_and_a_strict_http_expires():
    max_age = 3600
    storage = SharedCookieEncryptedCookieStorage(
        secret_key=_SESSION_SECRET_KEY,
        cookie_name=_SESSION_COOKIE_NAME,
        max_age=max_age,
    )
    session = await storage.new_session()
    session["AIOHTTP_SECURITY"] = "me@example.com"

    request = make_mocked_request("GET", "/", headers={"Host": "osparc.example.com"})
    response = web.StreamResponse()

    before = datetime.now(UTC)
    await storage.save_session(request, response, session)

    cookie = await _parse_response_cookie(request, response)
    assert cookie["max-age"] == "3600"

    # independent ground truth: expires must strictly parse as an RFC 9110 HTTP-date
    # (a format drift, e.g. ISO-8601, makes parsedate_to_datetime raise) and land
    # at now + max_age
    expires = parsedate_to_datetime(cookie["expires"])
    assert expires is not None
    if expires.tzinfo is None:  # HTTP-date carries no numeric offset; GMT zone is literal
        expires = expires.replace(tzinfo=UTC)
    delta = (expires - before).total_seconds()
    assert max_age - 5 < delta < max_age + 5, f"expires={cookie['expires']}, delta={delta}"
