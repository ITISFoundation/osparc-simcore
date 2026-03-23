from collections import defaultdict
from collections.abc import Callable, Sequence


def interleave_by_key[T](
    items: Sequence[T],
    key: Callable[[T], str],
) -> list[T]:
    """Reorder *items* so that entries sharing the same *key* are spread as far apart as possible.

    Groups items by *key*, then round-robins across groups (largest first)
    to maximise the gap between consecutive items with the same key.

    Example::

        >>> interleave_by_key(
        ...     ['a@gmail.com', 'b@gmail.com', 'c@gmail.com', 'd@yahoo.com', 'e@yahoo.com'],
        ...     key=lambda e: e.split('@')[1],
        ... )
        ['a@gmail.com', 'd@yahoo.com', 'b@gmail.com', 'e@yahoo.com', 'c@gmail.com']

    The three gmail addresses are spread apart with yahoo addresses interleaved between them.
    """
    if len(items) <= 2:  # noqa: PLR2004
        return list(items)

    by_key: dict[str, list[T]] = defaultdict(list)
    for item in items:
        by_key[key(item)].append(item)

    # Sort groups descending by size so the largest groups come first
    # in every round-robin pass, giving the most even spread.
    sorted_groups = sorted(by_key.values(), key=len, reverse=True)

    result: list[T] = []
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
