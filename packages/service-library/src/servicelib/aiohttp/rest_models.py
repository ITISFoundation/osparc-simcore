""" rest - common schema models and classes
"""

import attr

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
    logs: list[LogMessageType] = attr.Factory(list)
    errors: list[ErrorItemType] = attr.Factory(list)
    status: int = 400
    message: str = "Unexpected client error"


@attr.s(auto_attribs=True)
class FakeType:
    path_value: str
    query_value: str
    body_value: dict[str, str]


@attr.s(auto_attribs=True)
class HealthCheckType:
    name: str
    status: str
    api_version: str
    version: str


#  TODO: fix __all__
