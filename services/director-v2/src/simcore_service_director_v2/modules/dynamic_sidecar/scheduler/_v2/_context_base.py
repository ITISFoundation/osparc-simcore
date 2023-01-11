from abc import ABC, abstractmethod
from typing import Any, Optional

from fastapi import FastAPI


class ReservedContextKeys:
    APP: str = "app"

    WORKFLOW_NAME: str = "__workflow_name"
    WORKFLOW_ACTION_NAME: str = "__workflow_action_name"
    WORKFLOW_CURRENT_STEP_NAME: str = "__workflow_current_step_name"
    WORKFLOW_CURRENT_STEP_INDEX: str = "__workflow_current_step_index"

    EXCEPTION: str = "unexpected_runtime_exception"

    # reserved keys cannot be overwritten by the events
    RESERVED: set[str] = {
        APP,
        EXCEPTION,
        WORKFLOW_NAME,
        WORKFLOW_ACTION_NAME,
        WORKFLOW_CURRENT_STEP_NAME,
        WORKFLOW_CURRENT_STEP_INDEX,
    }

    # NOTE: objects pointed by these keys are just references
    # to local global values and never serialized
    STORED_LOCALLY: set[str] = {APP}


class ContextIOInterface(ABC):
    """
    Used to save/load the context in bulk.
    Useful for those types of stores which are not capable of guaranteeing
    data persistance between reboots. (eg: in memory implementation)
    Should become obsolete in the future if something like a Redis based
    store will be used.
    """

    @abstractmethod
    async def to_dict(self) -> dict[str, Any]:
        """returns the context of a store as a dictionary"""

    @classmethod
    @abstractmethod
    async def from_dict(
        cls, context: "ContextInterface", app: FastAPI, incoming: dict[str, Any]
    ) -> "ContextIOInterface":
        """returns an instance from incoming deserialized data"""


class ContextStorageInterface(ABC):
    """
    Base interface for saving and loading data from a store.
    """

    @abstractmethod
    async def save(self, key: str, value: Any) -> None:
        """saves value to sore"""

    @abstractmethod
    async def load(self, key: str) -> Optional[Any]:
        """load value from store"""

    @abstractmethod
    async def has_key(self, key: str) -> bool:
        """is True if key is in store"""

    @abstractmethod
    async def setup(self) -> None:
        """run storage specific initializers"""

    @abstractmethod
    async def teardown(self) -> None:
        """run storage specific halt and cleanup"""


class ContextInterface(ContextStorageInterface, ContextIOInterface):
    """
    This should be inherited when defining a new type of Context.
    """
