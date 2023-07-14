""" Implements BaseOpenAPIRequest and BaseOpenAPIResponse interfaces for aiohttp

"""
# mypy: ignore-errors

import logging
import re

from aiohttp import web
from openapi_core.wrappers.base import BaseOpenAPIRequest, BaseOpenAPIResponse
from werkzeug.datastructures import ImmutableMultiDict

log = logging.getLogger(__name__)

_CAPTURES = re.compile(r"\(\?P<([_a-zA-Z][_a-zA-Z0-9]+)>(.[^)]+)\)")
PARAMETERS_KEYS = ("path", "query", "header", "cookie")
PATH_KEY, QUERY_KEY, HEADER_KEY, COOKIE_KEY = PARAMETERS_KEYS


class AiohttpOpenAPIRequest(BaseOpenAPIRequest):
    wrappedcls = web.Request

    def __init__(self, request: web.Request, data: str):
        self._request = request
        self._body = data

    @staticmethod
    async def create(request: web.Request):
        data = await request.text()
        return AiohttpOpenAPIRequest(request, data)

    @property
    def host_url(self):
        url = self._request.url.origin()
        return str(url)

    @property
    def path(self):
        # [scheme:]//[user[:password]@]host[:port][/path][?query][#fragment]
        return str(self._request.path_qs)

    @property
    def method(self) -> str:
        return self._request.method.lower()

    @property
    def path_pattern(self):
        # match_info is a UrlMappingMatchInfo(dict, AbstractMatchInfo interface)
        match_info = self._request.match_info
        info = match_info.get_info()

        # if PlainResource then
        path_pattern = info.get("path")

        # if DynamicResource then whe need to undo the conversion to formatter and pattern
        if not path_pattern:
            formatter = info.get("formatter")
            re_pattern = info.get("pattern").pattern
            kargs = {}
            # TODO: create a test with '/my/tokens/{service}/'
            # TODO: create a test with '/my/tokens/{service:google|facebook}/'
            # TODO: create a test with '/my/tokens/{identifier:\d+}/'
            for key, value in _CAPTURES.findall(re_pattern):
                if value == "[^{}/]+":  # = no re in pattern
                    kargs[key] = "{%s}" % (key)
                else:
                    kargs[key] = f"{{{key}:{value}}}"
            path_pattern = formatter.format(**kargs)

        return path_pattern

    @property
    def parameters(self):
        rq = self._request

        # a dict view of arguments that matched the request
        # TODO: not sure
        view_args = dict(rq.match_info)

        # The parsed URL parameters (the part in the URL after the question mark).
        # a multidict proxy that is conterted into list of (key,value) tuples
        args = list(rq.query.items())

        # case-insensitive multidict proxy with all headers
        headers = rq.headers

        # A multidict of all request's cookies
        cookies = rq.cookies

        kpath, kquery, kheader, kcookie = PARAMETERS_KEYS
        return {
            kpath: view_args or {},
            kquery: ImmutableMultiDict(args or []),
            kheader: headers or {},
            kcookie: cookies or {},
        }

    @property
    def body(self) -> str:
        """Returns str with body content"""
        return self._body

    @property
    def mimetype(self) -> str:
        """Read-only property with content part of Content-Type header"""
        return self._request.content_type


class AiohttpOpenAPIResponse(BaseOpenAPIResponse):
    wrappedcls = web.Response

    def __init__(self, response: web.Response, data: str):
        self._response = response
        self._text = data

    @staticmethod
    async def create(response: web.Response):
        text = await response.text
        return AiohttpOpenAPIResponse(response, text)

    @property
    def body(self) -> str:
        return self._text

    # FIXME: not part of BaseOpenAPIResponse but used in openapi-core
    data = body

    @property
    def status_code(self) -> int:
        return self._response.status

    @property
    def mimetype(self):
        return self._response.content_type
