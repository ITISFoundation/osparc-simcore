from typing import Any

from ..api_schemas_webserver._base import OutputSchema
from ..notifications import ChannelType, TemplateName


class TemplateRefGet(OutputSchema):
    channel: ChannelType
    template_name: TemplateName


class NotificationsTemplateGet(OutputSchema):
    ref: TemplateRefGet
    variables_schema: dict[str, Any]
