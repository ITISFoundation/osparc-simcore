# pylint: disable=redefined-outer-name

import pytest
from simcore_service_dynamic_scheduler.services.p_scheduler._abc import (
    BaseStep,
)
from simcore_service_dynamic_scheduler.services.p_scheduler._models import (
    DagStepSequences,
    WorkflowDefinition,
    WorkflowName,
)
from simcore_service_dynamic_scheduler.services.p_scheduler._workflow import WorkflowManager, _get_step_sequence


class A(BaseStep): ...


class B(BaseStep): ...


class C(BaseStep): ...


class D(BaseStep): ...


@pytest.fixture
def dag_manager() -> WorkflowManager:
    return WorkflowManager()


@pytest.fixture
def workflow_name() -> WorkflowName:
    return "test-workflow"


def _get_base_steps(definition: WorkflowDefinition) -> set[type[BaseStep]]:
    steps: set[type[BaseStep]] = set()
    for step_type, requires_step_types in definition:
        steps.add(step_type)

        for required_step_type in requires_step_types:
            steps.add(required_step_type)

    return steps


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
                (A, []),
            ],
            DagStepSequences(apply=({f"{__name__}.A"},), revert=({f"{__name__}.A"},)),
            id="single-node-workflow",
        ),
        pytest.param(
            [
                (A, []),
                (B, []),
                (C, []),
                (D, []),
            ],
            DagStepSequences(
                apply=({f"{__name__}.A", f"{__name__}.B", f"{__name__}.C", f"{__name__}.D"},),
                revert=({f"{__name__}.A", f"{__name__}.B", f"{__name__}.C", f"{__name__}.D"},),
            ),
            id="no-requirements-workflow",
        ),
        pytest.param(
            [
                (A, []),
                (B, [A]),
                (C, [A]),
                (D, [B, C, A]),
            ],
            DagStepSequences(
                apply=({f"{__name__}.A"}, {f"{__name__}.B", f"{__name__}.C"}, {f"{__name__}.D"}),
                revert=({f"{__name__}.D"}, {f"{__name__}.B", f"{__name__}.C"}, {f"{__name__}.A"}),
            ),
            id="multi-node-workflow-with-requirements",
        ),
    ],
)
async def test__get_step_sequence(
    dag_manager: WorkflowManager, workflow_name: WorkflowName, workflow: WorkflowDefinition, expected: DagStepSequences
):
    dag_manager.register_workflow(workflow_name, workflow)
    await dag_manager.setup()

    assert dag_manager.get_workflow_step_sequences(workflow_name) == expected

    for base_step in _get_base_steps(workflow):
        retrieved = dag_manager.get_base_step(base_step.get_unique_reference())
        assert retrieved == base_step

    await dag_manager.teardown()


def test__get_step_sequence_raises_on_cycle():
    workflow_with_cycle: WorkflowDefinition = [
        (A, [C]),
        (B, [A]),
        (C, [B]),
    ]
    with pytest.raises(ValueError, match="not a DAG"):
        _get_step_sequence(workflow_with_cycle)


async def test_dag_manager_registers_unique_steps_only(dag_manager: WorkflowManager, workflow_name: WorkflowName):
    workflow_1: WorkflowDefinition = [
        (A, []),
        (B, [A]),
    ]
    workflow_2: WorkflowDefinition = [
        (A, [C]),
    ]
    for k, workflow in enumerate([workflow_1, workflow_2]):
        dag_manager.register_workflow(f"{workflow_name}_{k}", workflow)

    with pytest.raises(ValueError, match=f"'{A.get_unique_reference()}' already registered"):
        await dag_manager.setup()
