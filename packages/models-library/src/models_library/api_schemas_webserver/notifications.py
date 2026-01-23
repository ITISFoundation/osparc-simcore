from pydantic import BaseModel

from models_library.api_schemas_webserver._base import OutputSchema


class SearchTemplatesQueryParams(BaseModel):
    # NOTE: str because we support wildcards
    channel: str | None = None
    template_name: str | None = None


class NotificationsTemplateRefGet(OutputSchema):
    channel: str
    template_name: str


class NotificationsTemplateGet(OutputSchema):
    channel: str
    template_name: str
    variables_schema: dict[str, object]
