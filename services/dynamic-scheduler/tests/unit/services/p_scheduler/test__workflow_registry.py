# pylint: disable=redefined-outer-name

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from simcore_service_dynamic_scheduler.services.p_scheduler._abc import (
    BaseStep,
)
from simcore_service_dynamic_scheduler.services.p_scheduler._models import (
    KeyConfig,
    StepsSequence,
    WorkflowDefinition,
    WorkflowName,
)
from simcore_service_dynamic_scheduler.services.p_scheduler._workflow_registry import (
    WorkflowRegistry,
    _get_step_sequence,
)


@pytest.fixture
def workflow_registry() -> WorkflowRegistry:
    return WorkflowRegistry()


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
async def _registry_lifespan(registry: WorkflowRegistry) -> AsyncIterator[None]:
    await registry.setup()
    try:
        yield
    finally:
        await registry.shutdown()


def _get_name(base_step: type[BaseStep]) -> str:
    return f"{__name__}.{base_step.__name__}"


class SA(BaseStep):
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


class SB(BaseStep): ...


class SC(BaseStep): ...


class SD(BaseStep):
    @classmethod
    def apply_requests_inputs(cls) -> set[KeyConfig]:
        return {KeyConfig(name="from_initial_context_1"), KeyConfig(name="a_produced_apply")}

    @classmethod
    def apply_provides_outputs(cls) -> set[KeyConfig]:
        return {KeyConfig(name="d_produced_apply")}

    @classmethod
    def revert_requests_inputs(cls) -> set[KeyConfig]:
        return {KeyConfig(name="a_produced_revert")}

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
                    (SA, []),
                ],
            ),
            ({_get_name(SA)},),
            id="single-node-workflow",
        ),
        pytest.param(
            WorkflowDefinition(
                initial_context=set(),
                steps=[
                    (SA, []),
                    (SB, []),
                    (SC, []),
                ],
            ),
            ({_get_name(SA), _get_name(SB), _get_name(SC)},),
            id="no-requirements-workflow",
        ),
        pytest.param(
            WorkflowDefinition(
                initial_context={KeyConfig(name="from_initial_context_1")},
                steps=[
                    (SA, []),
                    (SB, [SA]),
                    (SC, [SA]),
                    (SD, [SB, SC, SA]),
                ],
            ),
            ({_get_name(SA)}, {_get_name(SB), _get_name(SC)}, {_get_name(SD)}),
            id="multi-node-workflow-with-requirements",
        ),
    ],
)
async def test__workflow_setup_ok(
    workflow_registry: WorkflowRegistry,
    workflow_name: WorkflowName,
    workflow: WorkflowDefinition,
    expected: StepsSequence,
):
    workflow_registry.register_workflow(workflow_name, workflow)

    async with _registry_lifespan(workflow_registry):
        assert workflow_registry.get_workflow_steps_sequence(workflow_name) == expected

        for base_step in _get_base_steps(workflow):
            retrieved = workflow_registry.get_base_step(base_step.get_unique_reference())
            assert retrieved == base_step


class FE(BaseStep):
    @classmethod
    def apply_provides_outputs(cls) -> set[KeyConfig]:
        return {KeyConfig(name="common_apply")}


class FF(FE): ...


class FG(BaseStep):
    @classmethod
    def revert_provides_outputs(cls) -> set[KeyConfig]:
        return {KeyConfig(name="common_revert")}


class FH(FG): ...


class FI(BaseStep):
    @classmethod
    def apply_requests_inputs(cls) -> set[KeyConfig]:
        return {KeyConfig(name="apply_missing_key")}


class FJ(BaseStep):
    @classmethod
    def revert_requests_inputs(cls) -> set[KeyConfig]:
        return {KeyConfig(name="revert_missing_key")}


@pytest.mark.parametrize(
    "workflow, expected_error_message",
    [
        pytest.param(
            WorkflowDefinition(
                initial_context=set(),
                steps=[
                    (FE, []),
                    (FF, []),
                ],
            ),
            "'common_apply' already added by a step in APPLY",
            id="parallel-steps-write-same-key",
        ),
        pytest.param(
            WorkflowDefinition(
                initial_context=set(),
                steps=[
                    (FG, []),
                    (FH, []),
                ],
            ),
            "'common_revert' already added by a step in REVERT",
            id="parallel-steps-write-same-key",
        ),
        pytest.param(
            WorkflowDefinition(
                initial_context={KeyConfig(name="from_initial_context_1", optional=True)},
                steps=[
                    (SA, []),
                ],
            ),
            "Initial context cannot have optional keys",
            id="optional-in-initial-context",
        ),
        pytest.param(
            WorkflowDefinition(
                initial_context=set(),
                steps=[
                    (FI, []),
                ],
            ),
            "'apply_missing_key' not present in APPLY sequence_context",
            id="missing-apply-inputs",
        ),
        pytest.param(
            WorkflowDefinition(
                initial_context=set(),
                steps=[
                    (FJ, []),
                ],
            ),
            "'revert_missing_key' not present in REVERT sequence_context",
            id="missing-revert-inputs",
        ),
    ],
)
async def test__workflow_setup_fails(
    workflow_registry: WorkflowRegistry,
    workflow_name: WorkflowName,
    workflow: WorkflowDefinition,
    expected_error_message: str,
):
    workflow_registry.register_workflow(workflow_name, workflow)

    with pytest.raises(ValueError, match=expected_error_message):
        async with _registry_lifespan(workflow_registry):
            ...


def test__get_step_sequence_raises_on_cycle():
    workflow_with_cycle: WorkflowDefinition = WorkflowDefinition(
        initial_context=set(),
        steps=[
            (SA, [SC]),
            (SB, [SA]),
            (SC, [SB]),
        ],
    )
    with pytest.raises(ValueError, match="not a DAG"):
        _get_step_sequence(workflow_with_cycle)


async def test_workflow_registry_registers_unique_steps_only(
    workflow_registry: WorkflowRegistry, workflow_name: WorkflowName
):
    workflow_1: WorkflowDefinition = WorkflowDefinition(
        initial_context=set(),
        steps=[
            (SA, []),
            (SB, [SA]),
        ],
    )
    workflow_2: WorkflowDefinition = WorkflowDefinition(
        initial_context=set(),
        steps=[
            (SA, []),  # same as in workflow_1
        ],
    )
    for k, workflow in enumerate([workflow_1, workflow_2]):
        workflow_registry.register_workflow(f"{workflow_name}_{k}", workflow)

    with pytest.raises(ValueError, match=f"'{SA.get_unique_reference()}' already registered"):
        await workflow_registry.setup()
