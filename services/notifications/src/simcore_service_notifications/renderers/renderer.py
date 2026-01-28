from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..models.preview import NotificationTemplatePreview
from ..models.template import NotificationsTemplate


@dataclass(frozen=True)
class NotificationsRenderer(ABC):
    @abstractmethod
    def preview_template(
        self,
        template: NotificationsTemplate,
        context: dict[str, Any],
    ) -> NotificationTemplatePreview: ...
