import itertools
from collections.abc import Generator, Iterable
from typing import Any, TypeVar

import toolz
from pydantic import NonNegativeInt

T = TypeVar("T")


def partition_gen(
    input_list: Iterable, *, slice_size: NonNegativeInt
) -> Generator[tuple[Any, ...], None, None]:
    """
    Given an iterable and the slice_size yields tuples containing
    slice_size elements in them.
    Inputs:
        input_list= [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
        slice_size = 5
    Outputs:
        [(1, 2, 3, 4, 5), (6, 7, 8, 9, 10), (11, 12, 13)]
    """
    if not input_list:
        yield ()

    yield from toolz.partition_all(slice_size, input_list)


def pairwise(iterable: Iterable[T]) -> Iterable[tuple[T, T]]:
    """
    s -> (s0,s1), (s1,s2), (s2, s3), ...
    NOTE: it requires at least 2 elements to produce a pair,
    otherwise an empty sequence will be returned
    """
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b, strict=False)
