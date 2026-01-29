from collections.abc import Awaitable, Callable

from .models import DagTemplate, StepId


class StepHandler:
    def __init__(
        self,
        *,
        do: Callable[..., Awaitable[None]],
        undo: Callable[..., Awaitable[None]],
    ) -> None:
        self.do = do
        self.undo = undo


_steps: dict[StepId, StepHandler] = {}
_workflows: dict[str, DagTemplate] = {}


def register_step(step_id: StepId, handler: StepHandler) -> None:
    _steps[step_id] = handler


def get_step(step_id: StepId) -> StepHandler:
    return _steps[step_id]


def register_workflow(template: DagTemplate) -> None:
    _workflows[template.workflow_id] = template


def get_workflow(workflow_id: str) -> DagTemplate:
    return _workflows[workflow_id]
