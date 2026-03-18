from abc import ABC, abstractmethod
from typing import Any

from models_library.notifications._notifications import NotificationsMessage


class ChannelHandler(ABC):
    """Base class for all channel-specific message handlers."""

    @staticmethod
    @abstractmethod
    def prepare_messages(message: NotificationsMessage) -> list[dict[str, Any]]:
        """Fan out a message model into per-recipient celery payloads."""
