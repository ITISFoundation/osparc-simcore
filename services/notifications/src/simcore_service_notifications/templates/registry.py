from models_library.notifications import ChannelType
from pydantic import BaseModel

from ..exceptions.errors import VariablesModelNotFoundError
from ..models.template import TemplateRef

_CONTEXT_MODELS: dict[TemplateRef, type[BaseModel]] = {}


def register_context_model(channel: ChannelType, template_name: str):
    def _(cls: type[BaseModel]):
        _CONTEXT_MODELS[TemplateRef(channel, template_name)] = cls
        return cls

    return _


def get_context_model(ref: TemplateRef) -> type[BaseModel]:
    context_model = _CONTEXT_MODELS.get(ref)
    if not context_model:
        raise VariablesModelNotFoundError(template_ref=ref)
    return context_model
