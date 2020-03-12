"""OpenAPI core contrib **aiohttp** requests module

Based in https://github.com/p1c2u/openapi-core/blob/master/openapi_core/contrib/requests/requests.py
"""
import re
from typing import Dict

from aiohttp.web import Request, UrlMappingMatchInfo
from openapi_core.validation.request.datatypes import OpenAPIRequest, RequestParameters
from six.moves.urllib.parse import urljoin
from werkzeug.datastructures import ImmutableMultiDict

PATH_PARAMETER_PATTERN = r"\(\?P<([_a-zA-Z][_a-zA-Z0-9]+)>(.[^)]+)\)"


class AiohttpOpenAPIRequestFactory:

    path_regex = re.compile(PATH_PARAMETER_PATTERN)

    @classmethod
    def eval_path_pattern(cls, match_info: UrlMappingMatchInfo) -> str:
        # match_info is a UrlMappingMatchInfo(dict, AbstractMatchInfo interface)

        info: Dict[str, str] = match_info.get_info()

        # if PlainResource then
        path_pattern: str = info.get("path", "")

        # if DynamicResource then whe need to undo the conversion to formatter and pattern
        if not path_pattern:
            formatter = info.get("formatter")
            re_pattern = info.get("pattern").pattern
            kargs = {}
            for key, value in cls.path_regex.findall(re_pattern):
                if value == "[^{}/]+":  # = no re in pattern
                    kargs[key] = "{%s}" % (key)
                else:
                    kargs[key] = "{%s:%s}" % (key, value)
            path_pattern = formatter.format(**kargs)

        return path_pattern

    @classmethod
    async def create(cls, request: Request) -> OpenAPIRequest:
        method: str = request.method.lower()

        mimetype: str = request.content_type

        # Case-insensitive multidict proxy with all headers
        header: Dict = request.headers or {}

        # The parsed URL parameters (the part in the URL after the question mark)
        # a multidict proxy that is conterted into list of (key,value) tuples
        query = ImmutableMultiDict(list(request.query.items()) or [])

        # A multidict of all request's cookies
        cookie: Dict = request.cookies or {}

        body: str = await request.text()

        path_pattern: str = cls.eval_path_pattern(request.match_info)

        full_url_pattern: str = urljoin(str(request.url.origin()), path_pattern)

        # FIXME: not sure. Review definitions!
        # a dict view of arguments that matched the request
        path_args = dict(request.match_info) or {}

        # openapi-core types
        parameters = RequestParameters(
            path=path_args, query=query, header=header, cookie=cookie
        )

        return OpenAPIRequest(
            full_url_pattern=full_url_pattern,
            method=method,
            parameters=parameters,
            body=body,
            mimetype=mimetype,
        )
