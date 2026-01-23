from typing import Any

from ...notifications import ChannelType, TemplateName


class NotificationsTemplateRefRpcGet:
    channel: ChannelType
    template_name: TemplateName


class NotificationsTemplateRpcGet:
    ref: NotificationsTemplateRefRpcGet
    variables_schema: dict[str, Any]
