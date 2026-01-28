"""Base context model for notification templates."""

from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import SkipJsonSchema


class BaseTemplateContext(BaseModel):
    product: SkipJsonSchema[dict[str, Any]]
