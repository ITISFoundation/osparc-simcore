from abc import ABC
from dataclasses import dataclass

from models_library.notifications import ChannelType, TemplateName
from pydantic import BaseModel


@dataclass(frozen=True)
class TemplateRef:
    """
    Identifies a template uniquely in the system.
    """

    channel: ChannelType
    template_name: TemplateName


@dataclass(frozen=True)
class NotificationTemplate(ABC):
    ref: TemplateRef
    context_model: type[BaseModel]

    parts: tuple[str, ...]
