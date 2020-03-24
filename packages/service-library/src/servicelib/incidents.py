from typing import Any, Callable, Generic, List, Optional, TypeVar

import attr


# UTILS ---

ItemT = TypeVar("ItemT")


@attr.s(auto_attribs=True)
class LimitedOrderedStack(Generic[ItemT]):
    """ Container designed only to keep the most
        relevant items (i.e called max) and drop
        everything else

        Can be used as base class for incidence registry
        A running app might have endless amount of incidence
        over-time and we aim only to keep the most relevant ones
        provided we have limited resources.
    """

    max_size: int = 100
    order_by: Optional[Callable[[ItemT], Any]] = None

    _items: List[ItemT] = attr.ib(init=False, default=attr.Factory(list))
    _hits: int = attr.ib(init=False, default=0)

    def __len__(self):
        # called also for __bool__
        return len(self._items)

    @property
    def hits(self):
        return self._hits

    @property
    def max_item(self) -> Optional[ItemT]:
        if self._items:
            return self._items[0]
        return None

    @property
    def min_item(self) -> Optional[ItemT]:
        if self._items:
            return self._items[-1]
        return None

    def append(self, item: ItemT):
        self._items.append(item)
        self._hits += 1

        # sort is based on the __lt__ defined in ItemT
        self._items = sorted(self._items, key=self.order_by, reverse=True)
        if len(self._items) > self.max_size:
            self._items.pop()  # min is dropped


# INCIDENT ISSUES ---


@attr.s(auto_attribs=True)
class BaseIncident:
    msg: str


@attr.s(auto_attribs=True)
class SlowCallback(BaseIncident):
    delay_secs: float
