from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State

from ..t_scheduler import WorkflowRegistry, get_workflow_registry


def _register_workflows(registry: WorkflowRegistry) -> None:
    """Register all production workflows.

    Add ``registry.register(...)`` calls here as new workflows are created.
    """
    _ = registry


async def t_scheduler_register_workflows_lifespan(app: FastAPI) -> AsyncIterator[State]:
    """Populate the registry with production workflows.

    Override this lifespan in tests to register test workflows instead.
    """
    _register_workflows(get_workflow_registry(app))
    yield {}
