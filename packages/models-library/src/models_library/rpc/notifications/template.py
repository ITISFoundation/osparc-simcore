from typing import Any

from pydantic import BaseModel


class NotificationsTemplateRefRpcGet(BaseModel):
    channel: str
    template_name: str


class NotificationsTemplateRpcGet(BaseModel):
    ref: NotificationsTemplateRefRpcGet
    variables_schema: dict[str, Any]
