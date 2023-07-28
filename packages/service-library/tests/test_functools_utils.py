# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import inspect

from servicelib.functools_utils import copy_func


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
