import inspect
from typing import Tuple, Union

from servicelib.functools_utils import copy_func


def test_copy_functions():
    # fixture
    def original_func(
        x: int, y: bool, *, z: Union[str, float, None] = None
    ) -> Tuple[int, Union[str, float, None]]:
        """some doc"""
        return 2 * x, z if y else "Foo"

    original_func.cache = [1, 2, 3]
    # ---

    copied_func = copy_func(original_func)

    assert copy_func is not original_func

    # but does and feel the same
    assert copied_func.__doc__ == original_func.__doc__
    assert copied_func.__name__ == "original_func"

    assert inspect.signature(original_func) == inspect.signature(copied_func)
    assert original_func(1, True, z=33) == copied_func(1, True, z=33)
    assert original_func.cache == copied_func.cache
