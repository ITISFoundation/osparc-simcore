import logging
from collections.abc import Callable, Coroutine
from copy import deepcopy
from typing import Any

from ._base_workflow import SagaWorkflow
from ._errors import WorkflowAlreadyRegisteredError, WorkflowNotFoundError

_logger = logging.getLogger(__name__)


class WorkflowRegistry:
    def __init__(self) -> None:
        self._workflows: dict[str, type[SagaWorkflow]] = {}
        self._activities: list[Callable[..., Coroutine[Any, Any, Any]]] = []

    def register(
        self,
        *,
        name: str,
        workflow_cls: type[SagaWorkflow],
    ) -> None:
        if name in self._workflows:
            raise WorkflowAlreadyRegisteredError(name=name)

        self._workflows[name] = workflow_cls
        for act in workflow_cls.get_activities():
            if act not in self._activities:
                self._activities.append(act)

        _logger.info(
            "Registered workflow %r (class=%s)",
            name,
            workflow_cls.__name__,
        )

    def get_workflow(self, name: str) -> type[SagaWorkflow]:
        if name not in self._workflows:
            raise WorkflowNotFoundError(name=name, available=list(self._workflows))
        return self._workflows[name]

    def get_temporalio_workflows(self) -> list[type[SagaWorkflow]]:
        return list(self._workflows.values())

    def get_registered_workflows(self) -> dict[str, type[SagaWorkflow]]:
        return deepcopy(self._workflows)

    def get_temporalio_activities(self) -> list[Callable[..., Coroutine[Any, Any, Any]]]:
        return list(self._activities)
