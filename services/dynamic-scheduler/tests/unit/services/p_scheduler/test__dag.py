# pylint: disable=redefined-outer-name

import pytest
from simcore_service_dynamic_scheduler.services.p_scheduler._dag import DagManager, _get_step_sequence
from simcore_service_dynamic_scheduler.services.p_scheduler._models import (
    DagStepSequences,
    WorkflowDefinition,
    WorkflowName,
)


@pytest.fixture
def dag_manager() -> DagManager:
    return DagManager()


@pytest.fixture
def workflow_name() -> WorkflowName:
    return "test-workflow"


@pytest.mark.parametrize(
    "workflow, expected",
    [
        pytest.param(
            [],
            DagStepSequences(apply=(), revert=()),
            id="empty-workflow",
        ),
        pytest.param(
            [
                ("A", []),
            ],
            DagStepSequences(apply=({"A"},), revert=({"A"},)),
            id="single-node-workflow",
        ),
        pytest.param(
            [
                ("A", []),
                ("B", []),
                ("C", []),
                ("D", []),
            ],
            DagStepSequences(apply=({"A", "B", "C", "D"},), revert=({"A", "B", "C", "D"},)),
            id="no-requirements-workflow",
        ),
        pytest.param(
            [
                ("A", []),
                ("B", ["A"]),
                ("C", ["A"]),
                ("D", ["B", "C", "A"]),
            ],
            DagStepSequences(apply=({"A"}, {"B", "C"}, {"D"}), revert=({"D"}, {"B", "C"}, {"A"})),
            id="multi-node-workflow-with-requirements",
        ),
    ],
)
async def test__get_step_sequence(
    dag_manager: DagManager, workflow_name: WorkflowName, workflow: WorkflowDefinition, expected: DagStepSequences
):
    dag_manager.register_workflow(workflow_name, workflow)
    await dag_manager.setup()
    assert dag_manager.get_workflow_step_sequences(workflow_name) == expected
    await dag_manager.teardown()


def test__get_step_sequence_raises_on_cycle():
    workflow_with_cycle: WorkflowDefinition = [
        ("A", ["C"]),
        ("B", ["A"]),
        ("C", ["B"]),
    ]
    with pytest.raises(ValueError, match="not a DAG"):
        _get_step_sequence(workflow_with_cycle)
