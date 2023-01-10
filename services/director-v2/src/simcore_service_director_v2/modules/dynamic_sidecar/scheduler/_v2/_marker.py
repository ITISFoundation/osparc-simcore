import inspect
from functools import wraps
from typing import Any, Callable

from ._errors import UnexpectedStepReturnTypeError


def mark_step(func: Callable) -> Callable:
    """
    Decorate a coroutine as an step.
    Return type must always be of type `dict[str, Any]`
    Stores input types in `.input_types` and return type
    in `.return_type` for later usage.
    """

    func_annotations = inspect.getfullargspec(func).annotations

    # ensure output type is correct, only support sone
    return_type = func_annotations.pop("return", None)
    if return_type != dict[str, Any]:
        raise UnexpectedStepReturnTypeError(type=return_type)

    @wraps(func)
    async def wrapped(*args, **kwargs) -> Any:
        return await func(*args, **kwargs)

    # store input and return types for later usage
    wrapped.return_type = return_type
    wrapped.input_types = func_annotations

    return wrapped
