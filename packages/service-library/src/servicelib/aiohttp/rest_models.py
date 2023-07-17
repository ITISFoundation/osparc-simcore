from dataclasses import dataclass, field


@dataclass
class LogMessageType:
    message: str
    level: str = "INFO"
    logger: str = "user"


@dataclass
class ErrorItemType:
    code: str
    message: str
    resource: str | None
    field: str | None

    @classmethod
    def from_error(cls, err: BaseException):
        return cls(
            code=err.__class__.__name__, message=str(err), resource=None, field=None
        )


@dataclass
class ErrorType:
    logs: list[LogMessageType] = field(default_factory=list)
    errors: list[ErrorItemType] = field(default_factory=list)
    status: int = 400
    message: str = "Unexpected client error"
