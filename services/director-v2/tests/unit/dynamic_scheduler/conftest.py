import pytest
from pytest import FixtureRequest
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._context_base import (
    ContextIOInterface,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._context_in_memory import (
    InMemoryContext,
)


@pytest.fixture(params=[InMemoryContext])
def context(request: FixtureRequest) -> ContextIOInterface:
    return request.param()
