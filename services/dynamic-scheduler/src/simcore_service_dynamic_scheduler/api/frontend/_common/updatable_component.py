from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from .base_display_model import BaseUpdatableDisplayModel

T = TypeVar("T", bound=BaseUpdatableDisplayModel)


class BaseUpdatableComponent(ABC, Generic[T]):
    def __init__(self, display_model: T):
        self.display_model = display_model

    @abstractmethod
    def add_to_ui(self) -> None:
        """creates ui elements inside the parent container"""
