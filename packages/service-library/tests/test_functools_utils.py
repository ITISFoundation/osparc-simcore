# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import inspect

import pytest
from servicelib.functools_utils import called_successfully_once, copy_func


def test_copy_functions():
    # fixture
    def original_func(
        x: int, y: bool, *, z: str | float | None = None
    ) -> tuple[int, str | float | None]:
        """some doc"""
        return 2 * x, z if y else "Foo"

    original_func.cache = [1, 2, 3]
    # ---

    copied_func = copy_func(original_func)

    assert copy_func is not original_func

    assert copied_func.__doc__ == original_func.__doc__
    assert inspect.signature(original_func) == inspect.signature(copied_func)

    # pylint: disable=not-callable
    # pylint: disable=no-member

    assert hasattr(copied_func, "cache")
    assert callable(copied_func)
    assert original_func(1, True, z=33) == copied_func(1, True, z=33)
    assert original_func.cache == copied_func.cache


def test_called_once():
    @called_successfully_once
    def init_something_once(v):
        if isinstance(v, Exception):
            raise v
        return v

    with pytest.raises(RuntimeError):
        init_something_once(RuntimeError())

    assert init_something_once(1) == 1
    assert init_something_once(1) is None
    assert init_something_once(2) is None
