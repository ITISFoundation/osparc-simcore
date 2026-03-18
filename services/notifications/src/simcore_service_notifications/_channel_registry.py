from typing import Any

from models_library.notifications import ChannelType
from models_library.notifications.errors import NotificationsUnsupportedChannelError


class ChannelRegistry[V]:
    """Generic registry mapping ChannelType to a value.

    Reusable across the service for any channel-keyed lookup
    (e.g. handler classes, content models).
    """

    def __init__(
        self,
        entries: dict[ChannelType, V],
    ) -> None:
        self._entries: dict[ChannelType, V] = dict(entries)

    def get(self, channel: ChannelType) -> V:
        """Retrieve the value for *channel*.

        Raises:
            NotificationsUnsupportedChannelError: If no entry is registered for *channel*.
        """
        try:
            return self._entries[channel]
        except KeyError:
            raise NotificationsUnsupportedChannelError(channel=channel) from None

    def __contains__(self, channel: Any) -> bool:
        return channel in self._entries
