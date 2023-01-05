# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

import pytest
from fastapi import FastAPI
from pytest import FixtureRequest
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._context_base import (
    ContextIOInterface,
    ReservedContextKeys,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._context_in_memory import (
    InMemoryContext,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._context_resolver import (
    ContextResolver,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._errors import (
    NotAllowedContextKeyError,
)


@pytest.fixture(params=[InMemoryContext])
def storage_context(request: FixtureRequest) -> type[ContextIOInterface]:
    return request.param


async def test_context_resolver_initialization(
    storage_context: type[ContextIOInterface],
):
    app = FastAPI()
    context_resolver = ContextResolver(
        storage_context, app=app, workflow_name="", state_name=""
    )
    await context_resolver.start()

    # check locally stored values are available
    for key in ReservedContextKeys.STORED_LOCALLY:
        assert key in context_resolver._local_storage
    assert app == context_resolver._local_storage[ReservedContextKeys.APP]

    await context_resolver.shutdown()


async def test_context_resolver_ignored_keys(
    storage_context: type[ContextIOInterface],
):
    context_resolver = ContextResolver(
        storage_context, app=FastAPI(), workflow_name="", state_name=""
    )
    await context_resolver.start()

    with pytest.raises(NotAllowedContextKeyError):
        await context_resolver.set(ReservedContextKeys.EXCEPTION, "value")

    await context_resolver.set(
        ReservedContextKeys.EXCEPTION, "value", set_reserved=True
    )

    await context_resolver.shutdown()
