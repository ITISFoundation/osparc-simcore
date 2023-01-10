from typing import Any, Callable, Optional

from pydantic import BaseModel, Field, validator

from ._errors import (
    NextActionNotInPlayCatalogException,
    OnErrorActionNotInPlayCatalogException,
)
from ._models import ActionName


class Action(BaseModel):
    """
    A sequence of steps (functions)
    """

    name: ActionName
    steps: list[Callable] = Field(
        ...,
        description=(
            "list awaitables marked as steps, the order in this list "
            "is the order in which steps will be executed"
        ),
    )

    next_action: Optional[ActionName] = Field(
        ...,
        description="optional, name of the action to run after this one",
    )
    on_error_action: Optional[ActionName] = Field(
        ...,
        description="optional, name of the action to run after this one raises an unexpected error",
    )

    @property
    def steps_names(self) -> list[str]:
        return [x.__name__ for x in self.steps]

    @validator("steps")
    @classmethod
    def ensure_all_marked_as_step(cls, steps):
        for step in steps:
            for attr_name in ("input_types", "return_type"):
                if not hasattr(step, attr_name):
                    raise ValueError(
                        f"Event handler {step.__name__} should expose `{attr_name}` "
                        "attribute. Was it decorated with @mark_step?"
                    )
            if type(getattr(step, "input_types")) != dict:
                raise ValueError(
                    f"`{step.__name__}.input_types` should be of type {dict}"
                )
            if getattr(step, "return_type") != dict[str, Any]:
                raise ValueError(
                    f"`{step.__name__}.return_type` should be of type {dict[str, Any]}"
                )
        return steps


class PlayCatalog:
    """contains Action entries which define links to `next_action` and `on_error_action`"""

    def __init__(self, *actions: Action) -> None:
        self._registry: dict[ActionName, Action] = {s.name: s for s in actions}
        for action in actions:
            if (
                action.on_error_action is not None
                and action.on_error_action not in self._registry
            ):
                raise OnErrorActionNotInPlayCatalogException(
                    action_name=action.name,
                    on_error_action=action.on_error_action,
                    play_catalog=self._registry,
                )
            if (
                action.next_action is not None
                and action.next_action not in self._registry
            ):
                raise NextActionNotInPlayCatalogException(
                    action_name=action.name,
                    next_action=action.next_action,
                    play_catalog=self._registry,
                )

    def __contains__(self, item: ActionName) -> bool:
        return item in self._registry

    def __getitem__(self, key: ActionName) -> Action:
        return self._registry[key]
