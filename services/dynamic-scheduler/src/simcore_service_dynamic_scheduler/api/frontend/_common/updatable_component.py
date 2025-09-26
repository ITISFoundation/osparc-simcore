from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from nicegui import ui
from nicegui.element import Element

from .base_display_model import BaseUpdatableDisplayModel

T = TypeVar("T", bound=BaseUpdatableDisplayModel)


class BaseUpdatableComponent(ABC, Generic[T]):
    def __init__(self, display_model: T):
        self.display_model = display_model

        self._parent: Element | None = None
        self.display_model.on_remove_from_ui(self._remove_from_ui)

    def _remove_from_ui(self) -> None:
        if self._parent is not None:
            self._parent.delete()
            self._parent = None

    def display(self) -> None:
        if self._parent is None:
            self._parent = ui.element()  # this is an empty div as a parent
        with self._parent:
            self._draw_ui()

    @abstractmethod
    def _draw_ui(self) -> None:
        """creates ui elements inside the parent container"""
