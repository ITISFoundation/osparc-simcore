import asyncio
import copy
import random
from collections import deque
from time import time
from typing import Any, Dict, List

import pytest

from servicelib.async_utils import run_sequentially_in_context


class LockedStore:
    __slots__ = ("_queue", "_lock")

    def __init__(self):
        self._queue = deque()
        self._lock = asyncio.Lock()

    async def push(self, item: Any):
        async with self._lock:
            self._queue.append(item)

    async def get_all(self) -> List[Any]:
        async with self._lock:
            return list(self._queue)


async def test_context_aware_dispatch() -> None:
    @run_sequentially_in_context(target_args=["c1", "c2", "c3"])
    async def orderly(c1: Any, c2: Any, c3: Any, control: Any) -> None:
        _ = (c1, c2, c3)
        sleep_interval = random.uniform(0, 0.01)
        await asyncio.sleep(sleep_interval)

        context = dict(c1=c1, c2=c2, c3=c3)
        await locked_stores[make_key_from_context(context)].push(control)

    def make_key_from_context(context: Dict) -> str:
        return ".".join([f"{k}:{v}" for k, v in context.items()])

    def make_context():
        return dict(
            c1=random.randint(0, 10), c2=random.randint(0, 10), c3=random.randint(0, 10)
        )

    contexts = [make_context() for _ in range(10)]

    locked_stores = {}
    expected_outcomes = {}
    for context in contexts:
        key = make_key_from_context(context)
        locked_stores[key] = LockedStore()
        expected_outcomes[key] = deque()

    tasks = deque()
    for control in range(1000):
        context = random.choice(contexts)
        key = make_key_from_context(context)
        expected_outcomes[key].append(control)

        params = copy.deepcopy(context)
        params["control"] = control

        task = asyncio.get_event_loop().create_task(orderly(**params))
        tasks.append(task)

    for task in tasks:
        await task

    for context in contexts:
        key = make_key_from_context(context)
        assert list(expected_outcomes[key]) == await locked_stores[key].get_all()


async def test_context_aware_function_sometimes_fails() -> None:
    class DidFailException(Exception):
        pass

    @run_sequentially_in_context(target_args=["will_fail"])
    async def sometimes_failing(will_fail: bool) -> None:
        if will_fail:
            raise DidFailException("I was instructed to fail")
        return True

    for x in range(100):
        raise_error = x % 2 == 0

        if raise_error:
            with pytest.raises(DidFailException):
                await sometimes_failing(raise_error)
        else:
            assert await sometimes_failing(raise_error) is True


async def test_context_aware_wrong_target_args_name() -> None:
    expected_param_name = "wrong_parameter"

    # pylint: disable=unused-argument
    @run_sequentially_in_context(target_args=[expected_param_name])
    async def target_function(the_param: Any) -> None:
        return None

    with pytest.raises(ValueError) as excinfo:
        await target_function("something")

    message = (
        f"Expected '{expected_param_name}' in "
        f"'{target_function.__name__}' arguments."
    )
    assert str(excinfo.value).startswith(message) is True


async def test_context_aware_measure_parallelism() -> None:
    # expected duration 1 second
    @run_sequentially_in_context(target_args=["control"])
    async def sleep_for(sleep_interval: float, control: Any) -> Any:
        await asyncio.sleep(sleep_interval)
        return control

    control_sequence = list(range(1000))
    sleep_duration = 0.5
    functions = [sleep_for(sleep_duration, x) for x in control_sequence]

    start = time()
    result = await asyncio.gather(*functions)
    elapsed = time() - start

    assert elapsed < sleep_duration * 2  # allow for some internal delay
    assert control_sequence == result


async def test_context_aware_measure_serialization() -> None:
    # expected duration 1 second
    @run_sequentially_in_context(target_args=["control"])
    async def sleep_for(sleep_interval: float, control: Any) -> Any:
        await asyncio.sleep(sleep_interval)
        return control

    control_sequence = [1 for _ in range(10)]
    sleep_duration = 0.1
    functions = [sleep_for(sleep_duration, x) for x in control_sequence]

    start = time()
    result = await asyncio.gather(*functions)
    elapsed = time() - start

    minimum_timelapse = (sleep_duration) * len(control_sequence)
    assert elapsed > minimum_timelapse
    assert control_sequence == result