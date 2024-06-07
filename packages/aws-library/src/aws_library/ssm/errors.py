import functools
import logging
from typing import Awaitable, Callable, ParamSpec, TypeVar

from botocore import exceptions as botocore_exc
from pydantic.errors import PydanticErrorMixin


class SSMRuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "SSM client unexpected error"


class SSMNotConnectedError(SSMRuntimeError):
    msg_template: str = "Cannot connect with SSM server"


class SSMAccessError(SSMRuntimeError):
    code = "SSM_access.error"
    msg_template: str = "Unexpected error while accessing SSM backend"


P = ParamSpec("P")
R = TypeVar("R")


def ssm_exception_handler(log: logging.Logger):
    """converts typical aiobotocore/boto exceptions to storage exceptions
    NOTE: this is a work in progress as more exceptions might arise in different
    use-cases
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return await func(*args, **kwargs)
            except botocore_exc.ClientError as exc:
                status_code = int(exc.response.get("Error", {}).get("Code", -1))
                operation_name = exc.operation_name

                match status_code, operation_name:
                    case _:
                        raise SSMAccessError from exc
            except botocore_exc.EndpointConnectionError as exc:
                raise SSMAccessError from exc

            except botocore_exc.BotoCoreError as exc:
                log.exception("Unexpected error in SSM client: ")
                raise SSMAccessError from exc

        return wrapper

    return decorator
