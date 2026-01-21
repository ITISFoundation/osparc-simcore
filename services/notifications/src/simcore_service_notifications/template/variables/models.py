from .base import BaseVariablesModel
from .registry import register_variables_model


@register_variables_model(channel="email", template_name="empty")
class EmptyVariablesModel(BaseVariablesModel):
    body: str
