from functools import cached_property
from typing import Generic, TypeAlias, TypeVar

from nicegui import ui
from nicegui.element import Element

from .base_display_model import BaseUpdatableDisplayModel
from .updatable_component import BaseUpdatableComponent

M = TypeVar("M", bound=BaseUpdatableDisplayModel)

Reference: TypeAlias = str


class SomeRenderer(Generic[M]):
    def __init__(self, component: type[BaseUpdatableComponent]) -> None:
        self.component = component

        self._added_models: dict[Reference, M] = {}
        self._rendered_models: dict[Reference, BaseUpdatableComponent] = (
            {}
        )  # TODO: might only need a set here

        self._parent: Element | None = None

    @cached_property
    def parent(self) -> Element:
        if self._parent is None:
            self._parent = ui.element()  # this is an empty div as a parent
        return self._parent

    def add_or_update_model(self, reference: Reference, model: M) -> None:
        if reference not in self._added_models:
            self._added_models[reference] = model
            self._render_component(reference)
        else:
            self._added_models[reference].update(model)

    def remove_model(self, reference: Reference) -> None:
        if reference in self._added_models:
            self._added_models[reference].remove_from_ui()
            del self._added_models[reference]
            del self._rendered_models[reference]

    def _render_to_parent(self) -> None:
        with self.parent:
            for reference in self._added_models:
                if reference not in self._rendered_models:
                    self._render_component(reference)

    def _render_component(self, reference: Reference) -> None:
        with self.parent:
            model = self._added_models[reference]
            component = self.component(model)
            component.display()
            self._rendered_models[reference] = component

    def display(self) -> None:
        self._render_to_parent()
