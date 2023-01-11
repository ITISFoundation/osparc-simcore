# pylint: disable=redefined-outer-name

import pytest
from pytest import FixtureRequest
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._context_base import (
    ContextInterface,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._context_in_memory import (
    InMemoryContext,
)


@pytest.fixture(params=[InMemoryContext])
def context_io_interface_type(request: FixtureRequest) -> type[ContextInterface]:
    return request.param


@pytest.fixture
def context(context_io_interface_type: type[ContextInterface]) -> ContextInterface:
    return context_io_interface_type()
