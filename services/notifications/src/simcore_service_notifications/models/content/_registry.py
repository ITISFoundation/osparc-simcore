from models_library.notifications import Channel

from ..._channel_registry import ChannelRegistry
from ._content import Content
from ._email import EmailContent

_CONTENT_MODELS: ChannelRegistry[type[Content]] = ChannelRegistry(
    {Channel.email: EmailContent},
)


def for_channel(channel: Channel) -> type[Content]:
    """Get content model class for a specific channel."""
    return _CONTENT_MODELS.get(channel)
