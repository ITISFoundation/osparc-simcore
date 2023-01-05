from abc import ABC, abstractmethod
from typing import Any, Optional


class ReservedContextKeys:
    APP: str = "app"

    WORKFLOW_NAME: str = "__workflow_name"
    WORKFLOW_STATE_NAME: str = "__workflow_state_name"
    WORKFLOW_CURRENT_EVENT_NAME: str = "__workflow_current_event_name"
    WORKFLOW_CURRENT_EVENT_INDEX: str = "__workflow_current_event_index"

    EXCEPTION: str = "_exception"

    # reserved keys cannot be overwritten by the event handlers
    RESERVED: set[str] = {
        APP,
        EXCEPTION,
        WORKFLOW_NAME,
        WORKFLOW_STATE_NAME,
        WORKFLOW_CURRENT_EVENT_NAME,
        WORKFLOW_CURRENT_EVENT_INDEX,
    }

    # NOTE: the objects pointed by these keys are just references
    # to local global values and never serialized
    STORED_LOCALLY: set[str] = {APP}


class ContextSerializerInterface(ABC):
    @abstractmethod
    async def serialize(self) -> dict[str, Any]:
        """returns the context of a store as a dictionary"""

    @abstractmethod
    async def deserialize(self, incoming: dict[str, Any]) -> None:
        """parses the incoming context and sends it to the store"""


class ContextStorageInterface(ABC):
    """
    Base interface for saving and loading data.
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
    async def start(self) -> None:
        """run storage specific initializers"""

    @abstractmethod
    async def shutdown(self) -> None:
        """run storage specific halt and cleanup"""
