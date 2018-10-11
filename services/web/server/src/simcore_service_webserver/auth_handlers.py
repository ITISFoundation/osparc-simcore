import typing

from aiohttp import web
import attr
from simcore_servicelib.openapi_validation import (validate_body,
                                                   validate_parameters,
                                                   PARAMETERS_KEYS)

from .settings.constants import APP_OAS_KEY


async def _extract_and_validate(request):
    spec = request.app[APP_OAS_KEY]

    # extract and validate against openapi specs
    parameters = await validate_parameters(spec, request)
    body = await validate_body(spec, request)

    kpath, kquery, kheader, kcookie = PARAMETERS_KEYS #pylint: disable=W0612

    return parameters[kpath], body


# api models --------------------------------
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



# handlers ----------------------
async def check_health(request: web.Request):
    # input
    params, body = await _extract_and_validate(request)

    assert not params
    assert not body

    # business logic
    data = HealthCheckType(
        name='simcore-director-service',
        status='SERVICE_RUNNING',
        api_version= '0.1.0-dev+NJuzzD9S',
        version='0.1.0-dev+N127Mfv9H')
    error = None

    # output
    return web.json_response({
        'data': attr.asdict(data),
        'error': error,
        })


async def check_action(request: web.Request):
    # input
    params, body = await _extract_and_validate(request)

    assert params
    assert body

    #form = RegistrationType.from_body(body)



async def auth_register(request: web.Request):
    # input
    params, body = await _extract_and_validate(request)

    assert not params
    form = RegistrationType.from_body(body)

    #if form.validate():
    #form.errors.append()

    # output
    data = LogMessageType()
    data.message = "True"
    error = form.get_error()

    return web.json_response({
        'data': data,
        'error': error,
        })




def auth_login(request: web.Request):
    """
     1. Receive email and password through a /login endpoint.
     2. Check the email and password hash against the database.
     3. Create a new refresh token and JWT access token.
     4. Return both.
    """
    pass


def auth_logout(request: web.Request):
    pass



def auth_confirmation(request: web.Request):
    pass


__all__ = (
    'auth_register',
    'auth_login',
    'auth_logout',
    'auth_confirmation'
)
