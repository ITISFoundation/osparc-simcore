import asyncio
from copy import deepcopy
from typing import Any, Final

from fastapi import FastAPI
from simcore_service_dynamic_scheduler.services.generic_scheduler import BaseStep
from simcore_service_dynamic_scheduler.services.generic_scheduler._core import Store
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

_RETRY_PARAMS: Final[dict[str, Any]] = {
    "wait": wait_fixed(0.1),
    "stop": stop_after_delay(10),
    "retry": retry_if_exception_type(AssertionError),
}

EXECUTED: Final[str] = "executed"
REVERTED: Final[str] = "reverted"


class BaseExpectedStepOrder:
    def __init__(self, *steps: type[BaseStep]) -> None:
        self.steps = steps

    def __len__(self) -> int:
        return len(self.steps)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(step.get_step_name() for step in self.steps)})"


class ExecuteSequence(BaseExpectedStepOrder):
    """steps appear in a sequence as EXECUTE"""


class ExecuteRandom(BaseExpectedStepOrder):
    """steps appear in any given order as EXECUTE"""


class RevertSequence(BaseExpectedStepOrder):
    """steps appear in a sequence as REVERT"""


class RevertRandom(BaseExpectedStepOrder):
    """steps appear in any given order as REVERT"""


def _assert_order_sequence(
    remaning_call_order: list[tuple[str, str]],
    steps: tuple[type[BaseStep], ...],
    *,
    expected: str,
) -> None:
    for step in steps:
        step_name, actual = remaning_call_order.pop(0)
        assert step_name == step.get_step_name()
        assert actual == expected


def _assert_order_random(
    remaning_call_order: list[tuple[str, str]],
    steps: tuple[type[BaseStep], ...],
    *,
    expected: str,
) -> None:
    steps_names = {step.get_step_name() for step in steps}
    for _ in steps:
        step_name, actual = remaning_call_order.pop(0)
        assert step_name in steps_names
        assert actual == expected
        steps_names.remove(step_name)


def _assert_expected_order(
    detected_order: list[tuple[str, str]],
    expected_order: list[BaseExpectedStepOrder],
    *,
    use_only_first_entries: bool,
    use_only_last_entries: bool,
) -> None:
    assert not (use_only_first_entries and use_only_last_entries)

    expected_order_length = sum(len(x) for x in expected_order)

    # below operations are destructive make a copy
    call_order = deepcopy(detected_order)

    if use_only_first_entries:
        call_order = call_order[:expected_order_length]
    if use_only_last_entries:
        call_order = call_order[-expected_order_length:]

    assert len(call_order) == expected_order_length

    for group in expected_order:
        if isinstance(group, ExecuteSequence):
            _assert_order_sequence(call_order, group.steps, expected=EXECUTED)
        elif isinstance(group, ExecuteRandom):
            _assert_order_random(call_order, group.steps, expected=EXECUTED)
        elif isinstance(group, RevertSequence):
            _assert_order_sequence(call_order, group.steps, expected=REVERTED)
        elif isinstance(group, RevertRandom):
            _assert_order_random(call_order, group.steps, expected=REVERTED)
        else:
            msg = f"Unknown {group=}"
            raise NotImplementedError(msg)
    assert not call_order, f"Left overs {call_order=}"


async def ensure_expected_order(
    detected_order: list[tuple[str, str]],
    expected_order: list[BaseExpectedStepOrder],
    *,
    use_only_first_entries: bool = False,
    use_only_last_entries: bool = False,
) -> None:
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            await asyncio.sleep(0)  # wait for event to trigger
            _assert_expected_order(
                detected_order,
                expected_order,
                use_only_first_entries=use_only_first_entries,
                use_only_last_entries=use_only_last_entries,
            )


async def _get_keys_in_store(app: FastAPI) -> set[str]:
    return set(await Store.get_from_app_state(app).redis.keys())


async def ensure_keys_in_store(app: FastAPI, *, expected_keys: set[str]) -> None:
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            keys_in_store = await _get_keys_in_store(app)
            assert keys_in_store == expected_keys
