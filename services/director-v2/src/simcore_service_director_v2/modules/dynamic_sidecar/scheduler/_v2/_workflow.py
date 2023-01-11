from itertools import chain

from ._action import Action
from ._errors import (
    NextActionNotInWorkflowException,
    OnErrorActionNotInWorkflowException,
)
from ._models import ActionName


class Workflow:
    """contains Action entries which define links to `next_action` and `on_error_action`"""

    def __init__(self, *actions: Action) -> None:
        self._registry: dict[ActionName, Action] = {s.name: s for s in actions}
        for action in actions:
            if (
                action.on_error_action is not None
                and action.on_error_action not in self._registry
            ):
                raise OnErrorActionNotInWorkflowException(
                    action_name=action.name,
                    on_error_action=action.on_error_action,
                    workflow=self._registry,
                )
            if (
                action.next_action is not None
                and action.next_action not in self._registry
            ):
                raise NextActionNotInWorkflowException(
                    action_name=action.name,
                    next_action=action.next_action,
                    workflow=self._registry,
                )

    def __contains__(self, item: ActionName) -> bool:
        return item in self._registry

    def __getitem__(self, key: ActionName) -> Action:
        return self._registry[key]

    def __add__(self, other: "Workflow") -> "Workflow":
        return Workflow(*(chain(self._registry.values(), other._registry.values())))
