from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any, Optional


class ReservedContextKeys(str, Enum):
    def _generate_next_value_(self, *_: Any) -> str:  # pylint:disable=arguments-differ
        return self.lower()

    APP = auto()

    WORKFLOW_NAME = auto()
    WORKFLOW_ACTION_NAME = auto()
    WORKFLOW_CURRENT_STEP_NAME = auto()
    WORKFLOW_CURRENT_STEP_INDEX = auto()

    UNEXPECTED_RUNTIME_EXCEPTION = auto()

    @classmethod
    def is_reserved(cls, key: str) -> bool:
        return key.upper() in cls.__members__

    @classmethod
    def is_stored_locally(cls, key: str) -> bool:
        return key in _STORED_LOCALLY


_STORED_LOCALLY: set[str] = {
    f"{ReservedContextKeys.APP}",
}


class _ContextIOInterface(ABC):
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

    @abstractmethod
    async def update(self, incoming: dict[str, Any]) -> None:
        """stores data from incoming deserialized data"""


class _ContextStorageInterface(ABC):
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


class ContextInterface(_ContextStorageInterface, _ContextIOInterface):
    """
    This should be inherited when defining a new type of Context.
    """
