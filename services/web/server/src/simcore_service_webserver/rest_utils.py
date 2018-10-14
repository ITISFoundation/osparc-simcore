""" Utilities

    Miscelaneous of functions and classes to build rest API sub-module
"""
import json
import typing
from typing import Dict

import attr
from aiohttp import web

#pylint: disable=W0611
from simcore_servicelib.openapi_validation import (COOKIE_KEY, HEADER_KEY,
                                                   PATH_KEY, QUERY_KEY,
                                                   validate_request)

from .settings.constants import APP_OAS_KEY


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


# api models --------------------------------
# NOTE: using these, optional and required fields are always transmitted!
# NOTE: make some attrs nullable by default!?

@attr.s(auto_attribs=True)
class RegistrationType:
    email: str
    password: str
    confirm: str

    @classmethod
    def from_body(cls, data): # struct-like unmarshalled data produced by
        # TODO: simplify
        return cls(email=data.email, password=data.password, confirm=data.confirm)


@attr.s(auto_attribs=True)
class LogMessageType:
    message: str
    level: str = 'INFO'
    logger: str = 'user'


@attr.s(auto_attribs=True)
class ErrorItemType:
    code: str
    message: str
    resource: str
    field: str

    @classmethod
    def from_error(cls, err: BaseException):
        item = cls( code = err.__class__.__name__,
         message=str(err),
         resource=None,
         field=None
        )
        return item


@attr.s(auto_attribs=True)
class ErrorType:
    logs: typing.List[LogMessageType] = attr.Factory(list)
    errors: typing.List[ErrorItemType] = attr.Factory(list)
    status: int = 400


@attr.s(auto_attribs=True)
class FakeType:
    path_value: str
    query_value: str
    body_value: typing.Dict[str, str]


@attr.s(auto_attribs=True)
class HealthCheckType:
    name: str
    status: str
    api_version: str
    version: str


#  TODO: fix __all__
