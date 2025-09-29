from abc import ABC, abstractmethod
from functools import cached_property

from nicegui import ui
from nicegui.element import Element


class ParentMixin:
    def __init__(self) -> None:
        self._parent: Element | None = None

    @staticmethod
    def _get_parent() -> Element:
        """overwrite to use a different parent element"""
        return ui.element()

    @cached_property
    def parent(self) -> Element:
        if self._parent is None:
            self._parent = self._get_parent()
        return self._parent

    def remove_parent(self) -> None:
        if self._parent is not None:
            self._parent.delete()
            self._parent = None


class DisplayaMixin(ABC):
    @abstractmethod
    def display(self) -> None:
        """create an ui element ad attach it to the current NiceGUI context"""
