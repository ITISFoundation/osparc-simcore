from models_library.notifications import ChannelType
from models_library.notifications.errors import NotificationsUnsupportedChannelError

from ._base import ChannelHandler
from ._email import EmailChannelHandler

_CHANNEL_HANDLERS: dict[ChannelType, type[ChannelHandler]] = {
    ChannelType.email: EmailChannelHandler,
    # add other channel handlers here (e.g. ChannelType.sms: SmsChannelHandler)
}


def for_channel(channel: ChannelType) -> type[ChannelHandler]:
    """Get the handler class for a specific channel.

    Raises:
        NotificationsUnsupportedChannelError: If no handler is registered for the channel.
    """
    if channel not in _CHANNEL_HANDLERS:
        raise NotificationsUnsupportedChannelError(channel=channel)
    return _CHANNEL_HANDLERS[channel]
