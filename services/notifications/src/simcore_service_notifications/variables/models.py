from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import SkipJsonSchema

from .registry import register_variables_model


class BaseVariablesModel(BaseModel):
    product: SkipJsonSchema[dict[str, Any]]


@register_variables_model(channel="email", template_name="empty")
class EmptyVariablesModel(BaseVariablesModel):
    body: str
