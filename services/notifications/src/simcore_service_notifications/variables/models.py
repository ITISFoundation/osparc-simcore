from typing import Any

from pydantic import BaseModel

from .registry import register_variables_model


class VariablesModel(BaseModel):
    product: dict[str, Any]


@register_variables_model(channel="email", template_name="empty")
class EmptyVariablesModel(VariablesModel):
    body: str
