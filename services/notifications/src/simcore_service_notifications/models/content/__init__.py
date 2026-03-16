from models_library.notifications import ChannelType

from ..._channel_registry import ChannelRegistry
from ._content import Content
from ._email import EmailContent

__all__: tuple[str, ...] = (
    "Content",
    "EmailContent",
    "for_channel",
)

_CONTENT_MODELS: ChannelRegistry[type[Content]] = ChannelRegistry(
    {ChannelType.email: EmailContent},
)


def for_channel(channel: ChannelType) -> type[Content]:
    """Get content model class for a specific channel."""
    return _CONTENT_MODELS.get(channel)
