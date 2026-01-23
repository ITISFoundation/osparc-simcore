from typing import Any

from pydantic import BaseModel

from ...notifications import ChannelType, TemplateName


class NotificationsTemplateRefRpcGet(BaseModel):
    channel: ChannelType
    template_name: TemplateName


class NotificationsTemplateRpcGet(BaseModel):
    ref: NotificationsTemplateRefRpcGet
    context_schema: dict[str, Any]
