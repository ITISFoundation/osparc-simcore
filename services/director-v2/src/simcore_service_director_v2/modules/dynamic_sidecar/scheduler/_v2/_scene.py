from typing import Any, Callable, Optional

from pydantic import BaseModel, Field, validator

from ._models import SceneName


class Scene(BaseModel):
    """
    A sequence of actions (functions)
    """

    name: SceneName
    actions: list[Callable] = Field(
        ...,
        description=(
            "list awaitables marked as actions, the order in this list "
            "is the order in which actions will be executed"
        ),
    )

    next_scene: Optional[SceneName] = Field(
        ...,
        description="optional, name of the scene to run after this one",
    )
    on_error_scene: Optional[SceneName] = Field(
        ...,
        description="optional, name of the scene to run after this one raises an unexpected error",
    )

    @property
    def actions_names(self) -> list[str]:
        return [x.__name__ for x in self.actions]

    @validator("actions")
    @classmethod
    def ensure_all_marked_as_action(cls, actions):
        for action in actions:
            for attr_name in ("input_types", "return_type"):
                if not hasattr(action, attr_name):
                    raise ValueError(
                        f"Event handler {action.__name__} should expose `{attr_name}` "
                        "attribute. Was it decorated with @mark_action?"
                    )
            if type(getattr(action, "input_types")) != dict:
                raise ValueError(
                    f"`{action.__name__}.input_types` should be of type {dict}"
                )
            if getattr(action, "return_type") != dict[str, Any]:
                raise ValueError(
                    f"`{action.__name__}.return_type` should be of type {dict[str, Any]}"
                )
        return actions


class PlayCatalog:
    """contains Scene entries which define links to `next_scene` and `on_error_scene`"""

    def __init__(self, *scenes: Scene) -> None:
        self._registry: dict[SceneName, Scene] = {s.name: s for s in scenes}

    def __contains__(self, item: SceneName) -> bool:
        return item in self._registry

    def __getitem__(self, key: SceneName) -> Scene:
        return self._registry[key]
