from abc import ABC, abstractmethod
from typing import Any


class ChannelHandler(ABC):
    """Base class for all channel-specific message handlers."""

    @staticmethod
    @abstractmethod
    def prepare_messages(message: dict[str, Any]) -> list[dict[str, Any]]:
        """Validate and fan out a raw message into per-recipient payloads."""
