from typing import Any

import pytest
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._action import (
    Action,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._errors import (
    NextActionNotInPlayCatalogException,
    OnErrorActionNotInPlayCatalogException,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._marker import (
    mark_step,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._workflow import (
    Workflow,
)


async def test_action_ok():
    @mark_step
    async def print_info() -> dict[str, Any]:
        print("some info")
        return {}

    @mark_step
    async def verify(x: float, y: int) -> dict[str, Any]:
        assert type(x) == float
        assert type(y) == int
        return {}

    INFO_CHECK = Action(
        name="test",
        steps=[
            print_info,
            verify,
        ],
        next_action=None,
        on_error_action=None,
    )
    assert INFO_CHECK


def test_workflow():
    ACTION_ONE_NAME = "one"
    ACTION_TWO_NAME = "two"
    ACTION_MISSING_NAME = "not_existing_action"

    action_one = Action(
        name=ACTION_ONE_NAME, steps=[], next_action=None, on_error_action=None
    )
    acton_two = Action(
        name=ACTION_TWO_NAME, steps=[], next_action=None, on_error_action=None
    )

    workflow = Workflow(
        action_one,
        acton_two,
    )

    # in operator
    assert ACTION_ONE_NAME in workflow
    assert ACTION_TWO_NAME in workflow
    assert ACTION_MISSING_NAME not in workflow

    # get key operator
    assert workflow[ACTION_ONE_NAME] == action_one
    assert workflow[ACTION_TWO_NAME] == acton_two
    with pytest.raises(KeyError):
        workflow[ACTION_MISSING_NAME]  # pylint:disable=pointless-statement


def test_workflow_missing_next_action():
    action = Action(
        name="some_name",
        steps=[],
        next_action="missing_next_action",
        on_error_action=None,
    )
    with pytest.raises(NextActionNotInPlayCatalogException):
        Workflow(action)


def test_workflow_missing_on_error_action():
    action = Action(
        name="some_name",
        steps=[],
        next_action=None,
        on_error_action="missing_on_error_action",
    )
    with pytest.raises(OnErrorActionNotInPlayCatalogException):
        Workflow(action)
