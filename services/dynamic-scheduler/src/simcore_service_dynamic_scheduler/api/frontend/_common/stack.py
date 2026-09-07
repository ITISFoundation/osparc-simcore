from typing import TypeVar

from ._mixins import DisplayaMixin, ParentMixin
from .base_component import BaseUpdatableComponent
from .base_display_model import BaseUpdatableDisplayModel

M = TypeVar("M", bound=BaseUpdatableDisplayModel)

type Reference = str


class UpdatableComponentStack[M: BaseUpdatableDisplayModel](DisplayaMixin, ParentMixin):
    """
    Renders `BaseUpdatableComponent` models via the provided `BaseUpdatableDisplayModel`
    Appends new elements to the parent container.
    """

    def __init__(self, component: type[BaseUpdatableComponent]) -> None:
        super().__init__()
        self.component = component

        self._added_models: dict[Reference, M] = {}
        self._rendered_models: set[Reference] = set()

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
            self._rendered_models.add(reference)

    def display(self) -> None:
        self._render_to_parent()

    def add_or_update_model(self, reference: Reference, display_model: M) -> None:
        """adds or updates and existing ui element form a given model"""
        if reference not in self._added_models:
            self._added_models[reference] = display_model
            self._render_component(reference)
        else:
            self._added_models[reference].update(display_model)

    def remove_model(self, reference: Reference) -> None:
        """removes a model from the ui via it's given reference"""
        if reference in self._added_models:
            self._added_models[reference].remove_from_ui()
            del self._added_models[reference]
            self._rendered_models.remove(reference)
