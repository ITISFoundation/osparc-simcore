from models_library.notifications import Channel

from ..._channel_registry import ChannelRegistry
from ._base import ChannelHandler
from ._email import EmailChannelHandler

_CHANNEL_HANDLERS: ChannelRegistry[type[ChannelHandler]] = ChannelRegistry(
    {Channel.email: EmailChannelHandler},
)


def for_channel(channel: Channel) -> type[ChannelHandler]:
    """Get the handler class for a specific channel.

    Raises:
        NotificationsUnsupportedChannelError: If no handler is registered for the channel.
    """
    return _CHANNEL_HANDLERS.get(channel)
