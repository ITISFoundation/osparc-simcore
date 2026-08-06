from abc import ABC, abstractmethod
from typing import Any

from models_library.notifications.rpc import Message

from ...core.settings import ApplicationSettings
from ...models.product import Product


class ChannelHandler(ABC):
    """Base class for all channel-specific message handlers."""

    @staticmethod
    @abstractmethod
    def prepare_messages(
        message: Message,
        *,
        product: Product,
        settings: ApplicationSettings,
    ) -> list[dict[str, Any]]:
        """Fan out a message model into per-recipient celery payloads."""
