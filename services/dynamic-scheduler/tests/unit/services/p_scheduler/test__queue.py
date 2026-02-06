# pylint: disable=redefined-outer-name

from asyncio import QueueFull, sleep
from collections.abc import AsyncIterable
from datetime import timedelta
from typing import Final

import pytest
from pydantic import NonNegativeFloat, NonNegativeInt
from simcore_service_dynamic_scheduler.services.p_scheduler._queue import BoundedPubSubQueue, get_consumer_count

_SLEEP_DURATION: Final[NonNegativeFloat] = timedelta(milliseconds=1).total_seconds()


@pytest.fixture
def queue_size() -> int:
    size = 40
    assert (size // 2) * 2 == size, "queue_size must be even for this test"
    return size


@pytest.fixture
async def queue(queue_size: int) -> AsyncIterable[BoundedPubSubQueue[str]]:
    queue = BoundedPubSubQueue[str](maxsize=queue_size)
    yield queue
    await queue.close()


async def test_queue_workflow(queue: BoundedPubSubQueue[str], queue_size: int) -> None:
    async def faster_consumer(msg: str) -> None:
        print("[F]", msg)
        await sleep(_SLEEP_DURATION)

    async def slower_consumer(msg: str) -> None:
        print("[S]", msg)
        await sleep(_SLEEP_DURATION * 4)

    # 1. fill up the queue to capacity
    for i in range(queue_size // 2):
        queue.put_nowait(f"put-np-wait-{i}")

    for i in range(queue_size // 2):
        await queue.put(f"async-put-{i}")

    # 2. raises when queue is full
    with pytest.raises(QueueFull):
        queue.put_nowait("queue-full")

    with pytest.raises(QueueFull):
        await queue.put("queue-full")

    # subscribe two consumers
    queue.subscribe(faster_consumer)
    queue.subscribe(slower_consumer)

    # wait until all messages processed
    await queue.join()


@pytest.mark.parametrize(
    "duration, max_burst, expected_workers",
    [
        pytest.param(timedelta(milliseconds=10), 5, 1, id="not-below-1"),
        pytest.param(timedelta(milliseconds=10), 20, 1, id="1-worker"),
        pytest.param(timedelta(milliseconds=200), 20, 4, id="more-workers"),
    ],
)
def test_get_consumer_count(duration: timedelta, max_burst: NonNegativeInt, expected_workers: NonNegativeInt) -> None:
    assert get_consumer_count(duration, max_burst) == expected_workers
