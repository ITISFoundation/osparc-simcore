# pylint: disable=redefined-outer-name

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from simcore_service_dynamic_scheduler.services.p_scheduler._abc import (
    BaseStep,
)
from simcore_service_dynamic_scheduler.services.p_scheduler._models import (
    KeyConfig,
    StepSequence,
    WorkflowDefinition,
    WorkflowName,
)
from simcore_service_dynamic_scheduler.services.p_scheduler._workflow import WorkflowManager, _get_step_sequence


@pytest.fixture
def dag_manager() -> WorkflowManager:
    return WorkflowManager()


@pytest.fixture
def workflow_name() -> WorkflowName:
    return "test-workflow"


def _get_base_steps(definition: WorkflowDefinition) -> set[type[BaseStep]]:
    steps: set[type[BaseStep]] = set()
    for step_type, requires_step_types in definition.steps:
        steps.add(step_type)

        for required_step_type in requires_step_types:
            steps.add(required_step_type)

    return steps


@asynccontextmanager
async def _manager_lifespan(manager: WorkflowManager) -> AsyncIterator[None]:
    await manager.setup()
    yield
    await manager.teardown()


class A(BaseStep):
    @classmethod
    def apply_requests_inputs(cls) -> set[KeyConfig]:
        return {KeyConfig(name="a_optional", optional=True)}

    @classmethod
    def apply_provides_outputs(cls) -> set[KeyConfig]:
        return {KeyConfig(name="a_produced_apply")}

    @classmethod
    def revert_requests_inputs(cls) -> set[KeyConfig]:
        return {KeyConfig(name="a_optional", optional=True)}

    @classmethod
    def revert_provides_outputs(cls) -> set[KeyConfig]:
        return {KeyConfig(name="a_produced_revert")}


class B(BaseStep): ...


class C(BaseStep): ...


class D(BaseStep):
    @classmethod
    def apply_requests_inputs(cls) -> set[KeyConfig]:
        return {KeyConfig(name="from_initial_context_1"), KeyConfig(name="a_produced_apply")}

    @classmethod
    def apply_provides_outputs(cls) -> set[KeyConfig]:
        return {KeyConfig(name="d_produced_apply")}

    @classmethod
    def revert_requests_inputs(cls) -> set[KeyConfig]:
        return {
            KeyConfig(name="a_produced_revert"),
            # KeyConfig(name="d_produced_revert"),    # fails
            # KeyConfig(name="d_produced_apply"),  # fails
        }

    @classmethod
    def revert_provides_outputs(cls) -> set[KeyConfig]:
        return {KeyConfig(name="d_produced_revert")}


@pytest.mark.parametrize(
    "workflow, expected",
    [
        pytest.param(
            WorkflowDefinition(initial_context=set(), steps=[]),
            (),
            id="empty-workflow",
        ),
        pytest.param(
            WorkflowDefinition(
                initial_context=set(),
                steps=[
                    (A, []),
                ],
            ),
            ({f"{__name__}.A"},),
            id="single-node-workflow",
        ),
        pytest.param(
            WorkflowDefinition(
                initial_context=set(),
                steps=[
                    (A, []),
                    (B, []),
                    (C, []),
                ],
            ),
            ({f"{__name__}.A", f"{__name__}.B", f"{__name__}.C"},),
            id="no-requirements-workflow",
        ),
        pytest.param(
            WorkflowDefinition(
                initial_context={KeyConfig(name="from_initial_context_1")},
                steps=[
                    (A, []),
                    (B, [A]),
                    (C, [A]),
                    (D, [B, C, A]),
                ],
            ),
            ({f"{__name__}.A"}, {f"{__name__}.B", f"{__name__}.C"}, {f"{__name__}.D"}),
            id="multi-node-workflow-with-requirements",
        ),
    ],
)
async def test__get_step_sequence(
    dag_manager: WorkflowManager, workflow_name: WorkflowName, workflow: WorkflowDefinition, expected: StepSequence
):
    dag_manager.register_workflow(workflow_name, workflow)

    async with _manager_lifespan(dag_manager):
        assert dag_manager.get_workflow_step_sequences(workflow_name) == expected

        for base_step in _get_base_steps(workflow):
            retrieved = dag_manager.get_base_step(base_step.get_unique_reference())
            assert retrieved == base_step


def test__get_step_sequence_raises_on_cycle():
    workflow_with_cycle: WorkflowDefinition = WorkflowDefinition(
        initial_context=set(),
        steps=[
            (A, [C]),
            (B, [A]),
            (C, [B]),
        ],
    )
    with pytest.raises(ValueError, match="not a DAG"):
        _get_step_sequence(workflow_with_cycle)


async def test_dag_manager_registers_unique_steps_only(dag_manager: WorkflowManager, workflow_name: WorkflowName):
    workflow_1: WorkflowDefinition = WorkflowDefinition(
        initial_context=set(),
        steps=[
            (A, []),
            (B, [A]),
        ],
    )
    workflow_2: WorkflowDefinition = WorkflowDefinition(
        initial_context=set(),
        steps=[
            (A, [C]),
        ],
    )
    for k, workflow in enumerate([workflow_1, workflow_2]):
        dag_manager.register_workflow(f"{workflow_name}_{k}", workflow)

    with pytest.raises(ValueError, match=f"'{A.get_unique_reference()}' already registered"):
        await dag_manager.setup()
