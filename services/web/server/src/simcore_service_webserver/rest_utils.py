""" Utilities

"""
import typing

from aiohttp import web
import attr
from simcore_servicelib.openapi_validation import (validate_body,
                                                   validate_parameters,
                                                   PARAMETERS_KEYS)

from .settings.constants import APP_OAS_KEY


async def extract_and_validate(request: web.Request):
    spec = request.app[APP_OAS_KEY]

    # extract and validate against openapi specs
    parameters = await validate_parameters(spec, request)
    body = await validate_body(spec, request)

    kpath, kquery, kheader, kcookie = PARAMETERS_KEYS #pylint: disable=W0612

    return parameters[kpath], parameters[kquery], body


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
