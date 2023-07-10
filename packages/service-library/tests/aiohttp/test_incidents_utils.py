# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import operator
from dataclasses import dataclass

from servicelib.aiohttp.incidents import BaseIncident, LimitedOrderedStack


def test_limited_ordered_stack():
    class IntsRegistry(LimitedOrderedStack[int]):
        pass

    reg = IntsRegistry(max_size=2)

    assert not reg

    reg.append(1)
    reg.append(5)
    assert reg._items == [5, 1]

    reg.append(3)
    reg.append(21)

    assert reg._items == [21, 5]

    assert reg.max_item == 21
    assert reg.min_item == 5
    assert len(reg) == reg.max_size


def test_incidents_stack():
    @dataclass
    class TestIncident(BaseIncident):
        gravity: int

    class IncidentsRegistry(LimitedOrderedStack[TestIncident]):
        pass

    incidents = IncidentsRegistry(max_size=2, order_by=operator.attrgetter("gravity"))

    assert not incidents  # __len__ == 0

    foo = TestIncident("foo", 0)
    bar = TestIncident("bar", 3)
    zoo = TestIncident("zoo", 4)

    incidents.append(foo)
    incidents.append(bar)
    incidents.append(zoo)

    assert incidents  # __len__ != 0
    assert len(incidents) == 2
    assert len(incidents) == incidents.max_size
    assert incidents.hits == 3

    assert incidents.max_item is zoo
    assert incidents.min_item is bar

    kuu = TestIncident("kuu", 22)
    incidents.append(kuu)

    assert incidents.max_item is kuu
    assert len(incidents) == 2
    assert incidents.hits == 4
