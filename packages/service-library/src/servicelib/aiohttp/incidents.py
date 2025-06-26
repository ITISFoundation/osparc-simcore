from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

ItemT = TypeVar("ItemT")


@dataclass
class LimitedOrderedStack(Generic[ItemT]):
    """Container designed only to keep the most
    relevant items (i.e called max) and drop
    everything else

    Can be used as base class for incidence registry
    A running app might have endless amount of incidence
    over-time and we aim only to keep the most relevant ones
    provided we have limited resources.
    """

    max_size: int = 100
    order_by: Callable[[ItemT], Any] | None = None

    _items: list[ItemT] = field(default_factory=list, init=False)
    _hits: int = field(default=0, init=False)

    def __len__(self) -> int:
        # called also for __bool__
        return len(self._items)

    def __iter__(self) -> Iterator[ItemT]:
        return iter(self._items)

    def clear(self) -> None:
        self._items.clear()
        self._hits = 0

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def max_item(self) -> ItemT | None:
        if self._items:
            return self._items[0]
        return None

    @property
    def min_item(self) -> ItemT | None:
        if self._items:
            return self._items[-1]
        return None

    def append(self, item: ItemT):
        self._items.append(item)
        self._hits += 1

        # sort is based on the __lt__ defined in ItemT
        extras: dict[str, Any] = {}
        if self.order_by is not None:
            extras["key"] = self.order_by
        self._items = sorted(self._items, reverse=True, **extras)

        if len(self._items) > self.max_size:
            self._items.pop()  # min is dropped


# INCIDENT ISSUES ---


@dataclass
class BaseIncident:
    msg: str


@dataclass
class SlowCallback(BaseIncident):
    delay_secs: float

    def __lt__(self, other: "SlowCallback") -> bool:
        """Enable sorting by delay_secs (shorter delays are considered 'less than' longer delays)"""
        if not isinstance(other, SlowCallback):
            return NotImplemented
        return self.delay_secs < other.delay_secs
