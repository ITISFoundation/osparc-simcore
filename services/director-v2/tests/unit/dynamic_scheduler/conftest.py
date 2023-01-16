# pylint: disable=redefined-outer-name

from typing import Awaitable

import pytest
from pytest import FixtureRequest
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._context_base import (
    ContextInterface,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._context_in_memory import (
    InMemoryContext,
)


@pytest.fixture(params=[InMemoryContext])
def context_interface_type(request: FixtureRequest) -> type[ContextInterface]:
    return request.param


@pytest.fixture
def context(context_interface_type: type[ContextInterface]) -> ContextInterface:
    return context_interface_type()


@pytest.fixture
def context_interface_factory(
    context_interface_type: type[ContextInterface],
) -> Awaitable[ContextInterface]:
    async def _factory() -> Awaitable[ContextInterface]:
        return context_interface_type()

    return _factory
