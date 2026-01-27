from models_library.notifications import ChannelType
from pydantic import BaseModel

from ..models.context import NotificationsContext
from ..models.template import NotificationsTemplateRef

_CONTEXT_MODELS: dict[NotificationsTemplateRef, type[BaseModel]] = {}


def register_context(channel: ChannelType, template_name: str):
    def _(cls: type[BaseModel]):
        _CONTEXT_MODELS[NotificationsTemplateRef(channel, template_name)] = cls
        return cls

    return _


def get_context_model(ref: NotificationsTemplateRef) -> type[BaseModel]:
    context_model = _CONTEXT_MODELS.get(ref)
    if not context_model:
        return NotificationsContext
    return context_model
