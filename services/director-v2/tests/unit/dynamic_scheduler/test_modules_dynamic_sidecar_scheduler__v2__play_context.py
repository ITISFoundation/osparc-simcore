# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

from typing import Any

import pytest
from fastapi import FastAPI
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._context_base import (
    ContextIOInterface,
    ReservedContextKeys,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._errors import (
    GetTypeMismatchError,
    NotAllowedContextKeyError,
    NotInContextError,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._workflow_context import (
    WorkflowContext,
)

PLAY_NAME = "test_play"
PLAY_ACTION_NAME = "test_play_action_name"

EXTRA_PLAY_DATA: dict[str, str] = {
    ReservedContextKeys.PLAY_CURRENT_STEP_INDEX: 0,
    ReservedContextKeys.PLAY_NAME: PLAY_NAME,
    ReservedContextKeys.PLAY_ACTION_NAME: PLAY_ACTION_NAME,
}


@pytest.fixture
def key_1() -> str:
    return "key_1"


@pytest.fixture
def app() -> FastAPI:
    return FastAPI()


@pytest.fixture
async def workflow_context(
    app: FastAPI, context: ContextIOInterface
) -> WorkflowContext:
    workflow_context = WorkflowContext(
        context=context, app=app, play_name=PLAY_NAME, action_name=PLAY_ACTION_NAME
    )
    await workflow_context.setup()
    yield workflow_context
    await workflow_context.teardown()


async def test_workflow_context_local_values(
    app: FastAPI, workflow_context: WorkflowContext
):
    # check all locally stored values are available
    for key in ReservedContextKeys.STORED_LOCALLY:
        assert key in workflow_context._local_storage

    for local_key, value_1, value_2, value_type in [
        # add future served below
        (ReservedContextKeys.APP, app, FastAPI(), FastAPI),
    ]:
        # check local getter
        assert value_1 == workflow_context._local_storage[local_key]
        assert value_1 == await workflow_context.get(local_key, value_type)
        # check local setter
        await workflow_context.set(local_key, value_2, set_reserved=True)
        assert value_2 == workflow_context._local_storage[local_key]


async def test_workflow_context_reserved_key(workflow_context: WorkflowContext):
    with pytest.raises(NotAllowedContextKeyError):
        await workflow_context.set(ReservedContextKeys.EXCEPTION, "value")

    await workflow_context.set(
        ReservedContextKeys.EXCEPTION, "value", set_reserved=True
    )


async def test_key_not_found_in_workflow_context(workflow_context: WorkflowContext):
    with pytest.raises(NotInContextError):
        await workflow_context.get("for_sure_I_am_missing", str)


async def test_key_get_wrong_type(key_1: str, workflow_context: WorkflowContext):
    await workflow_context.set(key_1, 4)
    with pytest.raises(GetTypeMismatchError):
        await workflow_context.get(key_1, str)


async def test_set_and_get_non_local(key_1: str, workflow_context: WorkflowContext):
    await workflow_context.set(key_1, 4)
    assert await workflow_context.get(key_1, int) == 4


async def test_to_dict(key_1: str, workflow_context: WorkflowContext):
    await workflow_context.set(key_1, 4)
    assert await workflow_context.to_dict() == {key_1: 4} | EXTRA_PLAY_DATA


async def test_from_dict(workflow_context: WorkflowContext):
    in_dict: dict[str, Any] = {"1": 1, "d": dict(me=1.1)}
    await workflow_context.from_dict(in_dict)
    assert await workflow_context.to_dict() == in_dict | EXTRA_PLAY_DATA
