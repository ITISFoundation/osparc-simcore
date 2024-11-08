# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import copy
import random
from collections import deque
from dataclasses import dataclass
from time import time
from typing import Any

import pytest
from faker import Faker
from servicelib.async_utils import (
    _sequential_jobs_contexts,
    run_sequentially_in_context,
)

RETRIES = 10
DIFFERENT_CONTEXTS_COUNT = 10


@pytest.fixture
def payload(faker: Faker) -> str:
    return faker.text()


@pytest.fixture
def expected_param_name() -> str:
    return "expected_param_name"


@pytest.fixture
def sleep_duration() -> float:
    return 0.01


class LockedStore:
    __slots__ = ("_queue", "_lock")

    def __init__(self):
        self._queue = deque()
        self._lock = asyncio.Lock()

    async def push(self, item: Any):
        async with self._lock:
            self._queue.append(item)

    async def get_all(self) -> list[Any]:
        async with self._lock:
            return list(self._queue)


def _compensate_for_slow_systems(number: float) -> float:
    # NOTE: in slower systems it is important to allow for enough time to pass
    # raising by one order of magnitude
    return number * 10


async def test_context_aware_dispatch(
    sleep_duration: float, ensure_run_in_sequence_context_is_empty: None, faker: Faker
) -> None:
    @run_sequentially_in_context(target_args=["c1", "c2", "c3"])
    async def orderly(c1: Any, c2: Any, c3: Any, control: Any) -> None:
        _ = (c1, c2, c3)
        await asyncio.sleep(sleep_duration)

        context = {"c1": c1, "c2": c2, "c3": c3}
        await locked_stores[make_key_from_context(context)].push(control)

    def make_key_from_context(context: dict) -> str:
        return ".".join([f"{k}:{v}" for k, v in context.items()])

    def make_context():
        return {
            "c1": faker.random_int(0, 10),
            "c2": faker.random_int(0, 10),
            "c3": faker.random_int(0, 10),
        }

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


async def test_context_aware_function_sometimes_fails(
    ensure_run_in_sequence_context_is_empty: None,
) -> None:
    class DidFailException(Exception):
        pass

    @run_sequentially_in_context(target_args=["will_fail"])
    async def sometimes_failing(will_fail: bool) -> bool:
        if will_fail:
            msg = "I was instructed to fail"
            raise DidFailException(msg)
        return True

    for x in range(100):
        raise_error = x % 2 == 0

        if raise_error:
            with pytest.raises(DidFailException):
                await sometimes_failing(raise_error)
        else:
            assert await sometimes_failing(raise_error) is True


async def test_context_aware_wrong_target_args_name(
    expected_param_name: str,
    ensure_run_in_sequence_context_is_empty: None,  # pylint: disable=unused-argument
) -> None:

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


async def test_context_aware_measure_parallelism(
    sleep_duration: float,
    ensure_run_in_sequence_context_is_empty: None,
) -> None:
    @run_sequentially_in_context(target_args=["control"])
    async def sleep_for(sleep_interval: float, control: Any) -> Any:
        await asyncio.sleep(sleep_interval)
        return control

    control_sequence = list(range(RETRIES))
    functions = [sleep_for(sleep_duration, x) for x in control_sequence]

    start = time()
    result = await asyncio.gather(*functions)
    elapsed = time() - start

    assert control_sequence == result
    assert elapsed < _compensate_for_slow_systems(sleep_duration)


async def test_context_aware_measure_serialization(
    sleep_duration: float,
    ensure_run_in_sequence_context_is_empty: None,
) -> None:
    # expected duration 1 second
    @run_sequentially_in_context(target_args=["control"])
    async def sleep_for(sleep_interval: float, control: Any) -> Any:
        await asyncio.sleep(sleep_interval)
        return control

    control_sequence = [1 for _ in range(RETRIES)]
    functions = [sleep_for(sleep_duration, x) for x in control_sequence]

    start = time()
    result = await asyncio.gather(*functions)
    elapsed = time() - start

    minimum_timelapse = (sleep_duration) * len(control_sequence)
    assert elapsed > minimum_timelapse
    assert control_sequence == result


async def test_nested_object_attribute(
    payload: str,
    ensure_run_in_sequence_context_is_empty: None,
) -> None:
    @dataclass
    class ObjectWithPropos:
        attr1: str = payload

    @run_sequentially_in_context(target_args=["object_with_props.attr1"])
    async def test_attribute(
        object_with_props: ObjectWithPropos, other_attr: int | None = None
    ) -> str:
        return object_with_props.attr1

    for _ in range(RETRIES):
        assert payload == await test_attribute(ObjectWithPropos())


async def test_different_contexts(
    payload: str,
    ensure_run_in_sequence_context_is_empty: None,
) -> None:
    @run_sequentially_in_context(target_args=["context_param"])
    async def test_multiple_context_calls(context_param: int) -> int:
        return context_param

    for _ in range(RETRIES):
        for i in range(DIFFERENT_CONTEXTS_COUNT):
            assert i == await test_multiple_context_calls(i)

    assert len(_sequential_jobs_contexts) == RETRIES
