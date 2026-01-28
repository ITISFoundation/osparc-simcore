from abc import ABC
from dataclasses import dataclass

from models_library.notifications import ChannelType, TemplateName
from notifications_library.context import BaseTemplateContext


@dataclass(frozen=True)
class NotificationsTemplateRef:
    """
    Identifies a template uniquely in the system.
    """

    channel: ChannelType
    template_name: TemplateName


@dataclass(frozen=True)
class NotificationsTemplate(ABC):
    ref: NotificationsTemplateRef
    context_model: type[BaseTemplateContext]

    parts: tuple[str, ...]
