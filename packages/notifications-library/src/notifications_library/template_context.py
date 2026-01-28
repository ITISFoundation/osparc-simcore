"""Base context model for notification templates."""

from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import SkipJsonSchema


class NotificationsTemplateContext(BaseModel):
    """Base context model that all template-specific contexts must inherit from."""

    product: SkipJsonSchema[dict[str, Any]]
