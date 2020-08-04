# pylint: disable=unused-wildcard-import
# pylint: disable=wildcard-import
# pylint: disable=unused-import, redefined-outer-name, protected-access

# TODO: should be fixed in #710. TEMPORARY SOLUTION

import asyncio
import base64
import hashlib
import json
import os
import sys
import traceback
import warnings
from types import SimpleNamespace, TracebackType
from typing import List  # noqa
from typing import (
    Any,
    Coroutine,
    Generator,
    Generic,
    Iterable,
    Mapping,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

import attr
from aiohttp import hdrs, http, payload
from aiohttp.abc import AbstractCookieJar
from aiohttp.client import *
from aiohttp.client import _SessionRequestContextManager
from aiohttp.client_exceptions import (
    ClientConnectionError,
    ClientConnectorCertificateError,
    ClientConnectorError,
    ClientConnectorSSLError,
    ClientError,
    ClientHttpProxyError,
    ClientOSError,
    ClientPayloadError,
    ClientProxyConnectionError,
    ClientResponseError,
    ClientSSLError,
    ContentTypeError,
    InvalidURL,
    ServerConnectionError,
    ServerDisconnectedError,
    ServerFingerprintMismatch,
    ServerTimeoutError,
    TooManyRedirects,
    WSServerHandshakeError,
)
from aiohttp.client_reqrep import (
    ClientRequest,
    ClientResponse,
    Fingerprint,
    RequestInfo,
    _merge_ssl_params,
)
from aiohttp.client_ws import ClientWebSocketResponse
from aiohttp.connector import BaseConnector, TCPConnector, UnixConnector
from aiohttp.cookiejar import CookieJar
from aiohttp.helpers import (
    DEBUG,
    PY_36,
    BasicAuth,
    CeilTimeout,
    TimeoutHandle,
    get_running_loop,
    proxies_from_env,
    sentinel,
    strip_auth_from_url,
)
from aiohttp.http import WS_KEY, HttpVersion, WebSocketReader, WebSocketWriter
from aiohttp.http_websocket import WSMessage  # noqa
from aiohttp.http_websocket import WSHandshakeError, ws_ext_gen, ws_ext_parse
from aiohttp.streams import FlowControlDataQueue
from aiohttp.tracing import Trace, TraceConfig
from aiohttp.typedefs import JSONEncoder, LooseCookies, LooseHeaders, StrOrURL
from multidict import CIMultiDict, MultiDict, MultiDictProxy, istr
from yarl import URL


def client_request(
    method: str,
    url: StrOrURL,
    *,
    params: Optional[Mapping[str, str]] = None,
    data: Any = None,
    json: Any = None,
    headers: LooseHeaders = None,
    skip_auto_headers: Optional[Iterable[str]] = None,
    auth: Optional[BasicAuth] = None,
    allow_redirects: bool = True,
    max_redirects: int = 10,
    compress: Optional[str] = None,
    chunked: Optional[bool] = None,
    expect100: bool = False,
    raise_for_status: Optional[bool] = None,
    read_until_eof: bool = True,
    proxy: Optional[StrOrURL] = None,
    proxy_auth: Optional[BasicAuth] = None,
    timeout: Union[ClientTimeout, object] = sentinel,
    cookies: Optional[LooseCookies] = None,
    version: HttpVersion = http.HttpVersion11,
    connector: Optional[BaseConnector] = None,
    loop: Optional[asyncio.AbstractEventLoop] = None
) -> _SessionRequestContextManager:
    """
        as aiohttp.client.request using a client session that does not decompress, i.e auto_decompress=False
    """
    connector_owner = False
    if connector is None:
        connector_owner = True
        connector = TCPConnector(loop=loop, force_close=True)

    session = ClientSession(
        loop=loop,
        cookies=cookies,
        version=version,
        timeout=timeout,
        connector=connector,
        connector_owner=connector_owner,
        auto_decompress=False,
    )

    return _SessionRequestContextManager(
        session._request(
            method,
            url,
            params=params,
            data=data,
            json=json,
            headers=headers,
            skip_auto_headers=skip_auto_headers,
            auth=auth,
            allow_redirects=allow_redirects,
            max_redirects=max_redirects,
            compress=compress,
            chunked=chunked,
            expect100=expect100,
            raise_for_status=raise_for_status,
            read_until_eof=read_until_eof,
            proxy=proxy,
            proxy_auth=proxy_auth,
        ),
        session,
    )
