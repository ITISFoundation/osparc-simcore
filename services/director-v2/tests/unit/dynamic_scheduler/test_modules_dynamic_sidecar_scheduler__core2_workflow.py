import pytest
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._action import (
    Action,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._errors import (
    NextActionNotInWorkflowException,
    OnErrorActionNotInWorkflowException,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._workflow import (
    Workflow,
)


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
    with pytest.raises(NextActionNotInWorkflowException):
        Workflow(action)


def test_workflow_missing_on_error_action():
    action = Action(
        name="some_name",
        steps=[],
        next_action=None,
        on_error_action="missing_on_error_action",
    )
    with pytest.raises(OnErrorActionNotInWorkflowException):
        Workflow(action)


def test_workflow_add():
    ACTION_ONE = "action_1"
    ACTION_TWO = "action_2"

    action_1 = Action(name=ACTION_ONE, steps=[], next_action=None, on_error_action=None)
    workflow_1 = Workflow(action_1)
    action_2 = Action(name=ACTION_TWO, steps=[], next_action=None, on_error_action=None)
    workflow_2 = Workflow(action_2)

    workflow = workflow_1 + workflow_2
    assert ACTION_ONE in workflow
    assert ACTION_TWO in workflow
    assert workflow[ACTION_ONE] == action_1
    assert workflow[ACTION_TWO] == action_2
