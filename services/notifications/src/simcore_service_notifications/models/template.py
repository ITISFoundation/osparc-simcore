from abc import ABC
from dataclasses import dataclass

from pydantic import BaseModel

from ..models.channel import ChannelType


@dataclass(frozen=True)
class TemplateRef:
    """
    Identifies a template uniquely in the system.
    """

    channel: ChannelType
    template_name: str


@dataclass(frozen=True)
class NotificationTemplate(ABC):
    ref: TemplateRef
    variables_model: type[BaseModel]

    parts: tuple[str, ...]
