from ...exceptions.errors import ContentModelNotFoundError
from ...models.channel import ChannelType
from .base import NotificationContent

CONTENTS: dict[ChannelType, type[NotificationContent]] = {}


def register_content(channel: ChannelType):
    def _(cls: type[NotificationContent]):
        CONTENTS[channel] = cls
        return cls

    return _


def get_content_cls(channel: ChannelType) -> type[NotificationContent]:
    content_model = CONTENTS.get(channel)
    if not content_model:
        raise ContentModelNotFoundError(channel=channel)
    return content_model
