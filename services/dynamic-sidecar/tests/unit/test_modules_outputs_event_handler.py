# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

import asyncio
from pathlib import Path
from typing import AsyncIterable
from unittest.mock import AsyncMock

import aioprocessing
import pytest
from aioprocessing.queues import AioQueue
from pydantic import PositiveFloat
from simcore_service_dynamic_sidecar.modules.outputs._context import OutputsContext
from simcore_service_dynamic_sidecar.modules.outputs._event_handler import (
    EventHandlerObserver,
    _EventHandlerProcess,
)
from simcore_service_dynamic_sidecar.modules.outputs._manager import OutputsManager


@pytest.fixture
def path_to_observe(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def outputs_port_keys() -> list[str]:
    return [f"port_key_{i}" for i in range(1, 10)]


@pytest.fixture
async def outputs_context(
    path_to_observe: Path, outputs_port_keys: list[str]
) -> OutputsContext:
    outputs_context = OutputsContext(path_to_observe)
    await outputs_context.set_file_type_port_keys(outputs_port_keys)
    return outputs_context


@pytest.fixture
async def outputs_manager(
    outputs_context: OutputsContext,
) -> AsyncIterable[OutputsManager]:
    outputs_manager = OutputsManager(
        outputs_context, io_log_redirect_cb=None, progress_cb=None
    )
    await outputs_manager.start()

    outputs_manager.set_all_ports_for_upload = AsyncMock()

    yield outputs_manager
    await outputs_manager.shutdown()


@pytest.fixture
def health_check_queue() -> AioQueue:
    return aioprocessing.AioQueue()


@pytest.fixture
def heart_beat_interval_s() -> PositiveFloat:
    return 0.01


async def test_event_handler_process_lifecycle(
    outputs_context: OutputsContext,
    health_check_queue: AioQueue,
    heart_beat_interval_s: PositiveFloat,
):
    observer_process = _EventHandlerProcess(
        outputs_context=outputs_context,
        health_check_queue=health_check_queue,
        heart_beat_interval_s=heart_beat_interval_s,
    )

    observer_process.start_process()
    await asyncio.sleep(heart_beat_interval_s * 10)
    observer_process.stop_process()

    observer_process.shutdown()


async def test_event_handler_observer_health_ok(
    outputs_context: OutputsContext,
    outputs_manager: OutputsManager,
    heart_beat_interval_s: PositiveFloat,
):
    observer_monitor = EventHandlerObserver(
        outputs_context=outputs_context,
        outputs_manager=outputs_manager,
        heart_beat_interval_s=heart_beat_interval_s,
    )

    await observer_monitor.start()
    await asyncio.sleep(heart_beat_interval_s * 10)

    await asyncio.sleep(observer_monitor.wait_for_heart_beat_interval_s * 10)
    await observer_monitor.stop()
    assert outputs_manager.set_all_ports_for_upload.call_count == 0


async def test_event_handler_observer_health_degraded(
    outputs_context: OutputsContext,
    outputs_manager: OutputsManager,
    heart_beat_interval_s: PositiveFloat,
):
    observer_monitor = EventHandlerObserver(
        outputs_context=outputs_context,
        outputs_manager=outputs_manager,
        heart_beat_interval_s=heart_beat_interval_s,
    )

    await observer_monitor.start()

    # emulate observer stuck
    observer_monitor._event_handler_process.stop_process()

    await asyncio.sleep(observer_monitor.wait_for_heart_beat_interval_s * 3)
    await observer_monitor.stop()
    assert outputs_manager.set_all_ports_for_upload.call_count >= 1
