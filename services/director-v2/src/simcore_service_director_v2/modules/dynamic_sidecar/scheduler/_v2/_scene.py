from typing import Any, Callable, Optional

from pydantic import BaseModel, Field, validator

from ._errors import (
    NextSceneNotInPlayCatalogException,
    OnErrorSceneNotInPlayCatalogException,
)
from ._models import SceneName


class Scene(BaseModel):
    """
    A sequence of steps (functions)
    """

    name: SceneName
    steps: list[Callable] = Field(
        ...,
        description=(
            "list awaitables marked as steps, the order in this list "
            "is the order in which steps will be executed"
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
    """contains Scene entries which define links to `next_scene` and `on_error_scene`"""

    def __init__(self, *scenes: Scene) -> None:
        self._registry: dict[SceneName, Scene] = {s.name: s for s in scenes}
        for scene in scenes:
            if (
                scene.on_error_scene is not None
                and scene.on_error_scene not in self._registry
            ):
                raise OnErrorSceneNotInPlayCatalogException(
                    scene_name=scene.name,
                    on_error_scene=scene.on_error_scene,
                    play_catalog=self._registry,
                )
            if scene.next_scene is not None and scene.next_scene not in self._registry:
                raise NextSceneNotInPlayCatalogException(
                    scene_name=scene.name,
                    next_scene=scene.next_scene,
                    play_catalog=self._registry,
                )

    def __contains__(self, item: SceneName) -> bool:
        return item in self._registry

    def __getitem__(self, key: SceneName) -> Scene:
        return self._registry[key]
