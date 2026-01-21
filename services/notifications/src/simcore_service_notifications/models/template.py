from abc import ABC
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class TemplateRef:
    """
    Identifies a template uniquely in the system.
    """

    channel: str
    template_name: str


@dataclass(frozen=True)
class NotificationTemplate(ABC):
    ref: TemplateRef
    variables_model: type[BaseModel]

    parts: tuple[str, ...]


@dataclass(frozen=True)
class EmailNotificationTemplate(NotificationTemplate):
    parts: tuple[str, ...] = ("subject", "body_html", "body_text")


@dataclass(frozen=True)
class SMSNotificationTemplate(NotificationTemplate):
    parts: tuple[str, ...] = ("text",)
