from typing import Any

from typing_extensions import (  # https://docs.pydantic.dev/latest/api/standard_library_types/#typeddict
    TypedDict,
)

Loc = tuple[int | str, ...]


class _ErrorDictRequired(TypedDict):
    """
    loc: identifies path in nested model e.g. ("parent", "child", "field", 0)
    type: set to code defined pydantic.errors raised upon validation
        (i.e. inside @validator decorated functions)

    Example:
        {
            "loc": (node_uuid, "complex", "real_part",)
            "msg": "Invalid real part, expected positive"
            "type": "value_error."
        }
    """

    loc: Loc
    msg: str
    type: str

    # SEE tests_errors for more details


class ErrorDict(_ErrorDictRequired, total=False):
    """Structured dataset returned by pydantic's ValidationError.errors() -> List[ErrorDict]"""

    ctx: dict[str, Any]


RABBITMQ_CLIENT_UNHEALTHY_MSG = "RabbitMQ client is in a bad state!"
REDIS_CLIENT_UNHEALTHY_MSG = "Redis cannot be reached!"


# NOTE: Here we do not just import as 'from pydantic.error_wrappers import ErrorDict'
# because that only works if TYPE_CHECKING=True.
__all__ = ("ErrorDict",)
