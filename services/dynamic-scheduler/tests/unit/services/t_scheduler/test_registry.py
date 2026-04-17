import pytest
from simcore_service_dynamic_scheduler.services.t_scheduler._base_workflow import (
    SagaWorkflow,
)
from simcore_service_dynamic_scheduler.services.t_scheduler._errors import (
    WorkflowAlreadyRegisteredError,
    WorkflowNotFoundError,
)
from simcore_service_dynamic_scheduler.services.t_scheduler._registry import (
    WorkflowRegistry,
)


def test_register_and_lookup(
    all_test_workflow_classes: list[type[SagaWorkflow]],
):
    registry = WorkflowRegistry()
    for wf_cls in all_test_workflow_classes:
        registry.register(name=wf_cls.__name__, workflow_cls=wf_cls)

    for wf_cls in all_test_workflow_classes:
        assert registry.get_workflow(wf_cls.__name__) is wf_cls

    assert set(all_test_workflow_classes) == set(registry.all_workflows())
    assert len(registry.all_activities()) > 0


def test_duplicate_name_raises(
    all_test_workflow_classes: list[type[SagaWorkflow]],
):
    registry = WorkflowRegistry()
    first, second, *_ = all_test_workflow_classes
    registry.register(name="dup", workflow_cls=first)

    with pytest.raises(WorkflowAlreadyRegisteredError, match="already registered"):
        registry.register(name="dup", workflow_cls=second)


def test_lookup_missing_raises():
    registry = WorkflowRegistry()

    with pytest.raises(WorkflowNotFoundError, match="not found"):
        registry.get_workflow("nonexistent")


def test_activities_deduplicated(
    all_test_workflow_classes: list[type[SagaWorkflow]],
):
    registry = WorkflowRegistry()
    for wf_cls in all_test_workflow_classes:
        registry.register(name=wf_cls.__name__, workflow_cls=wf_cls)

    # shared activities (step_a, undo_a, step_b, undo_b) should not be duplicated
    activities = registry.all_activities()
    assert len(activities) == len(set(activities))
