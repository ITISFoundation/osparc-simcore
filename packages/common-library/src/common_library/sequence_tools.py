from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import TypeVar

_T = TypeVar("_T")


def interleave_by_key(
    items: Sequence[_T],
    key: Callable[[_T], str],
) -> list[_T]:
    """Reorder *items* so that entries sharing the same *key* are spread as far apart as possible.

    Groups items by *key*, then round-robins across groups (largest first)
    to maximise the gap between consecutive items with the same key.
    """
    if len(items) <= 1:
        return list(items)

    by_key: dict[str, list[_T]] = defaultdict(list)
    for item in items:
        by_key[key(item)].append(item)

    # Sort groups descending by size so the largest groups come first
    # in every round-robin pass, giving the most even spread.
    sorted_groups = sorted(by_key.values(), key=len, reverse=True)

    result: list[_T] = []
    iterators = [iter(group) for group in sorted_groups]

    while iterators:
        next_round = []
        for it in iterators:
            value = next(it, None)
            if value is not None:
                result.append(value)
                next_round.append(it)
        iterators = next_round

    return result
