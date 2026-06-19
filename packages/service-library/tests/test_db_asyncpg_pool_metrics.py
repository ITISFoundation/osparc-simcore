# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access

from types import SimpleNamespace
from typing import cast

from prometheus_client import CollectorRegistry
from pytest_mock import MockerFixture
from servicelib.db_asyncpg_pool_metrics import DbPoolMetrics, setup_pool_metrics_instrumentation
from sqlalchemy.ext.asyncio import AsyncEngine


class _PoolWithCheckedOut:
    def __init__(self, *, size: int, max_overflow: int, checked_out: int) -> None:
        self._size = size
        self._max_overflow = max_overflow
        self._checked_out = checked_out

    def size(self) -> int:
        return self._size

    def checkedout(self) -> int:
        return self._checked_out


class _PoolWithoutCheckedOut:
    def __init__(self, *, size: int, max_overflow: int) -> None:
        self._size = size
        self._max_overflow = max_overflow

    def size(self) -> int:
        return self._size


def test_setup_pool_metrics_instrumentation_normal_path(mocker: MockerFixture):
    pool = _PoolWithCheckedOut(size=5, max_overflow=2, checked_out=3)
    engine = cast(AsyncEngine, SimpleNamespace(sync_engine=SimpleNamespace(pool=pool)))
    pool_metrics = DbPoolMetrics(
        namespace="test",
        subsystem="db",
        registry=CollectorRegistry(),
    )

    listen_mock = mocker.patch("servicelib.db_asyncpg_pool_metrics.event.listen")

    setup_pool_metrics_instrumentation(engine, pool_metrics)

    assert pool_metrics.pool_connections_size._value.get() == 5  # noqa: SLF001
    assert pool_metrics.pool_connections_total_capacity._value.get() == 7  # noqa: SLF001
    assert pool_metrics.pool_connections_checked_out._value.get() == 3  # noqa: SLF001
    assert pool_metrics.pool_connections_overflow._value.get() == 0  # noqa: SLF001
    assert pool_metrics.pool_utilization_ratio._value.get() == 3 / 7  # noqa: SLF001
    assert pool_metrics.pool_high_utilization_total._value.get() == 0  # noqa: SLF001

    assert listen_mock.call_count == 2
    checkout_callback = listen_mock.call_args_list[0].args[2]
    checkin_callback = listen_mock.call_args_list[1].args[2]

    pool._checked_out = 7  # noqa: SLF001
    checkout_callback(None, None, None)
    checkin_callback(None, None)

    assert pool_metrics.pool_connections_checked_out._value.get() == 7  # noqa: SLF001
    assert pool_metrics.pool_connections_overflow._value.get() == 2  # noqa: SLF001
    assert pool_metrics.pool_utilization_ratio._value.get() == 1.0  # noqa: SLF001
    assert pool_metrics.pool_high_utilization_total._value.get() == 2  # noqa: SLF001


def test_setup_pool_metrics_instrumentation_without_checkedout_method(mocker: MockerFixture):
    pool = _PoolWithoutCheckedOut(size=4, max_overflow=1)
    engine = cast(AsyncEngine, SimpleNamespace(sync_engine=SimpleNamespace(pool=pool)))
    pool_metrics = DbPoolMetrics(
        namespace="test",
        subsystem="db",
        registry=CollectorRegistry(),
    )

    listen_mock = mocker.patch("servicelib.db_asyncpg_pool_metrics.event.listen")

    setup_pool_metrics_instrumentation(engine, pool_metrics)

    assert pool_metrics.pool_connections_size._value.get() == 4  # noqa: SLF001
    assert pool_metrics.pool_connections_total_capacity._value.get() == 5  # noqa: SLF001
    assert pool_metrics.pool_connections_checked_out._value.get() == 0  # noqa: SLF001
    assert pool_metrics.pool_connections_overflow._value.get() == 0  # noqa: SLF001
    assert pool_metrics.pool_utilization_ratio._value.get() == 0  # noqa: SLF001
    assert pool_metrics.pool_high_utilization_total._value.get() == 0  # noqa: SLF001
    assert listen_mock.call_count == 2
