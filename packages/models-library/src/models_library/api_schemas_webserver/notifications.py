from typing import Any

from pydantic import BaseModel

from ..api_schemas_webserver._base import OutputSchema
from ..notifications import ChannelType, TemplateName


class SearchTemplatesQueryParams(BaseModel):
    # NOTE: str because we support wildcards
    channel: str | None = None
    template_name: str | None = None


class NotificationsTemplateRefGet(OutputSchema):
    channel: ChannelType
    template_name: TemplateName


class NotificationsTemplateGet(OutputSchema):
    ref: NotificationsTemplateRefGet
    context_schema: dict[str, Any]
