from ..exceptions.errors import ContentModelNotFoundError
from ..models.channel import ChannelType
from ..models.content import NotificationContent

_CONTENTS: dict[ChannelType, type[NotificationContent]] = {}


def register_content(channel: ChannelType):
    def _(cls: type[NotificationContent]):
        _CONTENTS[channel] = cls
        return cls

    return _


def get_content_cls(channel: ChannelType) -> type[NotificationContent]:
    content_model = _CONTENTS.get(channel)
    if not content_model:
        raise ContentModelNotFoundError(channel=channel)
    return content_model
