from typing import Any

from models_library.api_schemas_webserver._base import OutputSchema


class TemplateRefGet(OutputSchema):
    channel: str
    template_name: str


class NotificationTemplateGet(OutputSchema):
    ref: TemplateRefGet
    variables_schema: dict[str, Any]
