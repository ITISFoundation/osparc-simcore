# pylint: disable=redefined-outer-name

from typing import Any

import pytest
from pytest import FixtureRequest
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._context_in_memory import (
    InMemoryContext,
)


@pytest.fixture
def key_1() -> str:
    return "key_1"


@pytest.fixture(params=[1, "a", {"a": {"1": 2}}, set()])
def value(request: FixtureRequest) -> Any:
    return request.param


async def test_in_memory_context(key_1: str, value: Any):
    context = InMemoryContext()

    assert await context.has_key(key_1) is False
    await context.save(key_1, value)
    assert await context.has_key(key_1) is True

    stored_value = await context.load(key_1)
    assert stored_value == value

    # ensure serialization is working
    serialized_context = await context.to_dict()
    new_context = InMemoryContext()
    await new_context.from_dict(serialized_context)
    assert serialized_context == await new_context.to_dict()
