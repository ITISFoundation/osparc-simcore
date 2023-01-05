# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

from typing import Any

import pytest
from fastapi import FastAPI
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._context_base import (
    ContextIOInterface,
    ReservedContextKeys,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._context_resolver import (
    ContextResolver,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._errors import (
    GetTypeMismatchError,
    NotAllowedContextKeyError,
    NotInContextError,
)

WORKFLOW_NAME = "test_workflow"
WORKFLOW_STATE_NAME = "test_workflow_state_name"
EXTRA_DICT_DATA: dict[str, str] = {
    "__workflow_name": WORKFLOW_NAME,
    "__workflow_state_name": WORKFLOW_STATE_NAME,
}


@pytest.fixture
def key_1() -> str:
    return "key_1"


@pytest.fixture
def app() -> FastAPI:
    return FastAPI()


@pytest.fixture
async def context_resolver(
    app: FastAPI, storage_context: type[ContextIOInterface]
) -> ContextResolver:
    resolver = ContextResolver(
        storage_context,
        app=app,
        workflow_name=WORKFLOW_NAME,
        state_name=WORKFLOW_STATE_NAME,
    )
    await resolver.start()
    yield resolver
    await resolver.shutdown()


async def test_context_resolver_local_values(
    app: FastAPI, context_resolver: ContextResolver
):
    # check all locally stored values are available
    for key in ReservedContextKeys.STORED_LOCALLY:
        assert key in context_resolver._local_storage

    for local_key, value_1, value_2, value_type in [
        # add future served below
        (ReservedContextKeys.APP, app, FastAPI(), FastAPI),
    ]:
        # check local getter
        assert value_1 == context_resolver._local_storage[local_key]
        assert value_1 == await context_resolver.get(local_key, value_type)
        # check local setter
        await context_resolver.set(local_key, value_2, set_reserved=True)
        assert value_2 == context_resolver._local_storage[local_key]


async def test_context_resolver_reserved_key(context_resolver: ContextResolver):
    with pytest.raises(NotAllowedContextKeyError):
        await context_resolver.set(ReservedContextKeys.EXCEPTION, "value")

    await context_resolver.set(
        ReservedContextKeys.EXCEPTION, "value", set_reserved=True
    )


async def test_key_not_found_in_context(context_resolver: ContextResolver):
    with pytest.raises(NotInContextError):
        await context_resolver.get("for_sure_I_am_missing", str)


async def test_key_get_wrong_type(key_1: str, context_resolver: ContextResolver):
    await context_resolver.set(key_1, 4)
    with pytest.raises(GetTypeMismatchError):
        await context_resolver.get(key_1, str)


async def test_set_and_get_non_local(key_1: str, context_resolver: ContextResolver):
    await context_resolver.set(key_1, 4)
    assert await context_resolver.get(key_1, int) == 4


async def test_to_dict(key_1: str, context_resolver: ContextResolver):
    await context_resolver.set(key_1, 4)
    assert await context_resolver.to_dict() == {key_1: 4} | EXTRA_DICT_DATA


async def test_from_dict(context_resolver: ContextResolver):
    in_dict: dict[str, Any] = {"1": 1, "d": dict(me=1.1)}
    await context_resolver.from_dict(in_dict)
    assert await context_resolver.to_dict() == in_dict | EXTRA_DICT_DATA
