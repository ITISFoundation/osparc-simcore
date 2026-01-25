from models_library.notifications import ChannelType

from ..models.variables import BaseContextModel
from .registry import register_context_model


@register_context_model(channel=ChannelType.email, template_name="empty")
class EmptyTemplateContextModel(BaseContextModel):
    body: str
    subject: str
