# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

import asyncio
from asyncio import Queue as AsyncioQueue
from multiprocessing import Queue
from pathlib import Path

import pytest
from pydantic import PositiveFloat
from simcore_service_dynamic_sidecar.modules.outputs_watcher._observer import (
    ObserverMonitor,
    _ObserverProcess,
)


@pytest.fixture
def path_to_observe(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def outputs_port_keys() -> list[str]:
    return [f"port_key_{i}" for i in range(1, 10)]


@pytest.fixture
def events_queue() -> Queue:
    return Queue()


@pytest.fixture
def health_check_queue() -> Queue:
    return Queue()


@pytest.fixture
def health_queue() -> AsyncioQueue:
    return AsyncioQueue()


@pytest.fixture
def heart_beat_interval_s() -> PositiveFloat:
    return 0.01


@pytest.fixture
def detection_interval(heart_beat_interval_s: PositiveFloat) -> PositiveFloat:
    return heart_beat_interval_s * 10


async def test_observer_process_start_shutdown(
    path_to_observe: Path,
    outputs_port_keys: list[str],
    events_queue: Queue,
    health_check_queue: Queue,
    heart_beat_interval_s: PositiveFloat,
):
    observer_process = _ObserverProcess(
        path_to_observe=path_to_observe,
        outputs_port_keys=outputs_port_keys,
        events_queue=events_queue,
        health_check_queue=health_check_queue,
        heart_beat_interval_s=heart_beat_interval_s,
    )

    observer_process.start()
    await asyncio.sleep(heart_beat_interval_s * 10)
    observer_process.stop()
    observer_process.join()


async def test_observer_monitor_health_ok(
    path_to_observe: Path,
    outputs_port_keys: list[str],
    events_queue: Queue,
    health_queue: AsyncioQueue,
    heart_beat_interval_s: PositiveFloat,
):
    observer_monitor = ObserverMonitor(
        path_to_observe=path_to_observe,
        outputs_port_keys=outputs_port_keys,
        health_queue=health_queue,
        events_queue=events_queue,
        heart_beat_interval_s=heart_beat_interval_s,
    )

    await observer_monitor.start()
    await asyncio.sleep(heart_beat_interval_s * 10)
    await observer_monitor.stop()
    assert events_queue.qsize() == 0


async def test_observer_monitor_health_degraded(
    path_to_observe: Path,
    outputs_port_keys: list[str],
    events_queue: Queue,
    health_queue: AsyncioQueue,
    heart_beat_interval_s: PositiveFloat,
):

    observer_monitor = ObserverMonitor(
        path_to_observe=path_to_observe,
        outputs_port_keys=outputs_port_keys,
        health_queue=health_queue,
        events_queue=events_queue,
        heart_beat_interval_s=heart_beat_interval_s / 10,
    )

    await observer_monitor.start()
    await asyncio.sleep(observer_monitor.wait_for_heart_beat_interval_s)

    # emulate observer stuck
    observer_monitor._observer_process.stop()

    await asyncio.sleep(observer_monitor.wait_for_heart_beat_interval_s * 10)
    await observer_monitor.stop()

    assert health_queue.qsize() == 1
