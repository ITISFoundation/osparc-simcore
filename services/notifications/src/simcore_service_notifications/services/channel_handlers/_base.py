from abc import ABC, abstractmethod
from typing import Any

from models_library.notifications.rpc import EmailContact, Message
from models_library.products import ProductName


class ChannelHandler(ABC):
    """Base class for all channel-specific message handlers."""

    @staticmethod
    @abstractmethod
    def prepare_messages(
        message: Message,
        *,
        resolved_from: EmailContact | None = None,
        product_name: ProductName,
    ) -> list[dict[str, Any]]:
        """Fan out a message model into per-recipient celery payloads."""
