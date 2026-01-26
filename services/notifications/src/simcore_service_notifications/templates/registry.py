from models_library.notifications import ChannelType
from pydantic import BaseModel

from ..models.template import TemplateRef
from ..models.variables import BaseContextModel

_CONTEXT_MODELS: dict[TemplateRef, type[BaseModel]] = {}


def register_context_model(channel: ChannelType, template_name: str):
    def _(cls: type[BaseModel]):
        _CONTEXT_MODELS[TemplateRef(channel, template_name)] = cls
        return cls

    return _


def get_context_model(ref: TemplateRef) -> type[BaseModel]:
    context_model = _CONTEXT_MODELS.get(ref)
    if not context_model:
        # Return a default BaseContextModel for templates without explicit registration
        # This allows templates to be discovered without requiring explicit registration
        return BaseContextModel
    return context_model
