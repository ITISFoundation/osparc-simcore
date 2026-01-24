from typing import Any

from models_library.notifications import ChannelType

from ..exceptions.errors import ContentModelNotFoundError

_CONTENTS: dict[ChannelType, type[Any]] = {}


def register_content(channel: ChannelType):
    def _(cls: type[Any]):
        _CONTENTS[channel] = cls
        return cls

    return _


def get_content_cls(channel: ChannelType) -> type[Any]:
    content_model = _CONTENTS.get(channel)
    if not content_model:
        raise ContentModelNotFoundError(channel=channel)
    return content_model
