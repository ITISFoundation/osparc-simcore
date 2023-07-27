import functools
import types
from typing import Callable


def copy_func(f):
    # SEE https://stackoverflow.com/questions/13503079/how-to-create-a-copy-of-a-python-function
    g = types.FunctionType(
        f.__code__,
        f.__globals__,
        name=f.__name__,
        argdefs=f.__defaults__,
        closure=f.__closure__,
    )
    g = functools.update_wrapper(g, f)
    g.__kwdefaults__ = f.__kwdefaults__
    return g


def called_successfully_once(func: Callable):
    """Decorator to ensure only one successful call"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not wrapper.called:
            r = func(*args, **kwargs)
            wrapper.called = True
            return r
        return None

    wrapper.called = False
    return wrapper
