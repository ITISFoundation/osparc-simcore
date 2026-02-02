from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from fastapi import FastAPI

if TYPE_CHECKING:
    from ._models import DagNodeUniqueReference


class BaseStep(ABC):
    @classmethod
    def get_unique_reference(cls) -> "DagNodeUniqueReference":
        return f"{cls.__module__}.{cls.__name__}"

    @classmethod
    @abstractmethod
    async def apply(cls, app: FastAPI) -> None:
        """actions that construct/create resources in the system"""

    @classmethod
    @abstractmethod
    async def revert(cls, app: FastAPI) -> None:
        """actions that destroy/remove resources from the system"""
