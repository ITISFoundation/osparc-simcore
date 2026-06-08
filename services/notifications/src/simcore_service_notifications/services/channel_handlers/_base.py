from abc import ABC, abstractmethod
from typing import Any

from models_library.notifications.rpc import EmailContact, Message


class ChannelHandler(ABC):
    """Base class for all channel-specific message handlers."""

    @staticmethod
    @abstractmethod
    def prepare_messages(message: Message, *, resolved_from: EmailContact | None = None) -> list[dict[str, Any]]:
        """Fan out a message model into per-recipient celery payloads."""
