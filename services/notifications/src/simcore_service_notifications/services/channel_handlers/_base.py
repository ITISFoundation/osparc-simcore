from abc import ABC, abstractmethod
from typing import Any

from models_library.notifications.rpc import Message

from ...core.settings import ApplicationSettings
from ...models.product import Product


class ChannelHandler[MessageT: Message](ABC):
    """Base class for all channel-specific message handlers.

    Parameterized by the message model the channel consumes: the dispatcher
    selects the handler from message.channel, so the per-channel narrowing
    is decided at dispatch, not inside a handler.
    """

    @staticmethod
    @abstractmethod
    def prepare_messages(
        message: MessageT,
        *,
        product: Product,
        settings: ApplicationSettings,
    ) -> list[dict[str, Any]]:
        """Fan out a message model into per-recipient celery payloads."""
