""" Utilities

    Miscelaneous of functions and classes to build rest API sub-module
"""
import json
from typing import Dict

import attr
from aiohttp import web

from .constants import APP_OAS_KEY
#pylint: disable=W0611
from .openapi_validation import (COOKIE_KEY, HEADER_KEY, PATH_KEY, QUERY_KEY,
                                 validate_request)
from .rest_models import ErrorItemType, ErrorType


class EnvelopeFactory:
    """
        Creates a { 'data': , 'error': } envelop for response payload

        as suggested in https://medium.com/studioarmix/learn-restful-api-design-ideals-c5ec915a430f
    """
    def __init__(self, data=None, error=None):
        enveloped = {'data': data, 'error': error}
        for key, value in enveloped.items():
            if value is not None and not isinstance(value, dict):
                enveloped[key] = attr.asdict(value)
        self._envelope = enveloped

    def as_dict(self) -> Dict:
        return self._envelope

    def as_text(self) -> str:
        return json.dumps(self.as_dict())

    as_data = as_dict


async def extract_and_validate(request: web.Request):
    """
        Extracts validated parameters in path, query and body

    Can raise '400 Bad Request': indicates that the server could not understand the request due to invalid syntax
    See https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400
    """
    spec = request.app[APP_OAS_KEY]
    assert spec is not None

    params, body, errors = await validate_request(request, spec)

    if errors:
        error = ErrorType(
            errors=[ErrorItemType.from_error(err) for err in errors],
            status=web.HTTPBadRequest.status_code
        )
        raise web.HTTPBadRequest(
            reason="Failed request validation against API specs",
            text=EnvelopeFactory(error=error).as_text(),
            content_type='application/json',
            )

    return params[PATH_KEY], params[QUERY_KEY], body


#  TODO: fix __all__
