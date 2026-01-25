from models_library.notifications import ChannelType

from ..models.variables import BaseVariablesModel
from .registry import register_context_model


@register_context_model(channel=ChannelType.email, template_name="empty")
class EmptyTemplateVariablesModel(BaseVariablesModel):
    body: str
    subject: str
