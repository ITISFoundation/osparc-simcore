from abc import abstractmethod
from typing import Generic, TypeVar

from ._mixins import DisplayaMixin, ParentMixin
from .base_display_model import BaseUpdatableDisplayModel

M = TypeVar("M", bound=BaseUpdatableDisplayModel)


class BaseUpdatableComponent(DisplayaMixin, ParentMixin, Generic[M]):
    def __init__(self, display_model: M):
        super().__init__()

        self.display_model = display_model
        self.display_model.on_remove_from_ui(self.remove_parent)

    def display(self) -> None:
        with self.parent:
            self._draw_ui()

    @abstractmethod
    def _draw_ui(self) -> None:
        """creates ui elements inside the parent container"""
