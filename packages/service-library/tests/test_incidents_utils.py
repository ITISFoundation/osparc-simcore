# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint: disable=protected-access
import operator

import attr

from servicelib.incidents import BaseIncident, LimitedOrderedStack


def test_limited_ordered_stack():
    class IntsRegistry(LimitedOrderedStack[int]):
        pass

    reg = IntsRegistry(max_size=2)

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
    @attr.s(auto_attribs=True)
    class TestIncident(BaseIncident):
        gravity: int

    class IncidentsRegistry(LimitedOrderedStack[TestIncident]):
        pass

    reg = IncidentsRegistry(max_size=2, order_by=operator.attrgetter("gravity"))

    foo = TestIncident("foo", 0)
    bar = TestIncident("bar", 3)
    zoo = TestIncident("zoo", 4)

    reg.append(foo)
    reg.append(bar)
    reg.append(zoo)

    assert len(reg) == 2
    assert len(reg) == reg.max_size
    assert reg.hits == 3

    assert reg.max_item is zoo
    assert reg.min_item is bar

    kuu = TestIncident("kuu", 22)
    reg.append(kuu)

    assert reg.max_item is kuu
    assert len(reg) == 2
    assert reg.hits == 4
