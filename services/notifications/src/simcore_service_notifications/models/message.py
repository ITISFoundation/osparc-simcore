from collections.abc import Sequence
from dataclasses import dataclass

from ..template.content.models import NotificationContent
from .template import TemplateRef


@dataclass(frozen=True)
class NotificationMessage[C: NotificationContent]:
    template: TemplateRef
    recipients: Sequence[str]  # GCR: define recipient model
    content: C
