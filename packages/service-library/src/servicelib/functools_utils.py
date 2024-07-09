import functools
import types
from collections.abc import Callable
from typing import Any, cast


def copy_func(f: Callable[..., Any]) -> Callable[..., Any]:
    # SEE https://stackoverflow.com/questions/13503079/how-to-create-a-copy-of-a-python-function
    g = types.FunctionType(
        f.__code__,
        f.__globals__,
        name=f.__name__,
        argdefs=f.__defaults__,
        closure=f.__closure__,
    )
    g = cast(types.FunctionType, functools.update_wrapper(g, f))
    g.__kwdefaults__ = f.__kwdefaults__
    return g
