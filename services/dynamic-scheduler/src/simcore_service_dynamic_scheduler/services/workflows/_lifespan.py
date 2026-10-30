from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State

from ..t_scheduler import WorkflowRegistry, get_workflow_registry
from ._healthcheck_workflow import HealthcheckWorkflow
from ._names import WorkflowNames


def _register_workflows(registry: WorkflowRegistry) -> None:
    """Register all production workflows.

    Add ``registry.register(...)`` calls here as new workflows are created.
    """
    registry.register(name=WorkflowNames.HEALTHCHECK, workflow_cls=HealthcheckWorkflow)


async def t_scheduler_register_workflows_lifespan(app: FastAPI) -> AsyncIterator[State]:
    _register_workflows(get_workflow_registry(app))
    yield {}
