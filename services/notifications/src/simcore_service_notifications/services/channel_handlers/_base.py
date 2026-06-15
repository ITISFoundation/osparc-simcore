from abc import ABC, abstractmethod
from typing import Any

from models_library.notifications.rpc import Message
from models_library.products import ProductName

from ...core.settings import ProductToSMTPSettings
from ...models.product import Product


class ChannelHandler(ABC):
    """Base class for all channel-specific message handlers."""

    @staticmethod
    @abstractmethod
    def prepare_messages(
        message: Message,
        *,
        product_name: ProductName,
        product_data: Product,
        smtp_settings: ProductToSMTPSettings,
    ) -> list[dict[str, Any]]:
        """Fan out a message model into per-recipient celery payloads."""
