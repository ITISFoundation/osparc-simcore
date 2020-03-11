""" rest - common schema models and classes

UNDER DEVELOPMENT
"""
import attr
import typing
import warnings


warnings.warn("DO NOT USE IN PRODUCTION, STILL UNDER DEVELOPMENT")

# NOTE: using these, optional and required fields are always transmitted!
# NOTE: make some attrs nullable by default!?


@attr.s(auto_attribs=True)
class LogMessageType:
    message: str
    level: str = "INFO"
    logger: str = "user"


@attr.s(auto_attribs=True)
class ErrorItemType:
    code: str
    message: str
    resource: str
    field: str

    @classmethod
    def from_error(cls, err: BaseException):
        item = cls(
            code=err.__class__.__name__, message=str(err), resource=None, field=None
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
