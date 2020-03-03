"""OpenAPI core contrib aiohttp requests module"""
import re
from typing import Dict

from aiohttp.web import Request, UrlMappingMatchInfo
from openapi_core.validation.request.datatypes import (OpenAPIRequest,
                                                       RequestParameters)
from six.moves.urllib.parse import urljoin
from werkzeug.datastructures import ImmutableMultiDict

PATH_PARAMETER_PATTERN = r'\(\?P<([_a-zA-Z][_a-zA-Z0-9]+)>(.[^)]+)\)'


class AiohttpOpenAPIRequestFactory(object):

    path_regex = re.compile(PATH_PARAMETER_PATTERN)

    @classmethod
    def eval_path_pattern(cls, match_info: UrlMappingMatchInfo ) -> str:
        # match_info is a UrlMappingMatchInfo(dict, AbstractMatchInfo interface)

        info: Dict[str,str] = match_info.get_info()

        # if PlainResource then
        path_pattern = info.get('path')

        # if DynamicResource then whe need to undo the conversion to formatter and pattern
        if not path_pattern:
            formatter = info.get('formatter')
            re_pattern = info.get('pattern').pattern
            kargs = {}
            # TODO: create a test with '/my/tokens/{service}/'
            # TODO: create a test with '/my/tokens/{service:google|facebook}/'
            # TODO: create a test with '/my/tokens/{identifier:\d+}/'
            for key, value in cls.path_regex.findall(re_pattern):
                if value == '[^{}/]+': # = no re in pattern
                    kargs[key] = "{%s}" % (key)
                else:
                    kargs[key] = "{%s:%s}" % (key, value)
            path_pattern = formatter.format(**kargs)

        return path_pattern


    @classmethod
    async def create(cls, request: Request) -> OpenAPIRequest:

        body: str = await request.text()
        method: str = request.method.lower()
        path_pattern: str = cls.eval_path_pattern(request.match_info)

        # a dict view of arguments that matched the request
        # TODO: not sure
        path_args = dict(request.match_info) or {}

        # The parsed URL parameters (the part in the URL after the question mark).
        # a multidict proxy that is conterted into list of (key,value) tuples
        query = ImmutableMultiDict( list(request.query.items()) or [] )

        parameters = RequestParameters(
            path=path_args,
            query=query,
            header=request.headers or {}, # case-insensitive multidict proxy with all headers
            cookie=request.cookies or {}, # A multidict of all request's cookies
        )

        full_url_pattern = urljoin(
            str(request.url.origin()), path_pattern)

        return OpenAPIRequest(
            full_url_pattern=full_url_pattern,
            method=method,
            parameters=parameters,
            body=body,
            mimetype=request.content_type,
        )
