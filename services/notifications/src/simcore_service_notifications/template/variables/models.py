from ...models.channel import ChannelType
from .base import BaseVariablesModel
from .registry import register_variables_model


@register_variables_model(channel=ChannelType.email, template_name="empty")
class EmptyVariablesModel(BaseVariablesModel):
    body: str
