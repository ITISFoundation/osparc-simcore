from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..models.preview import NotificationPreview
from ..models.template import NotificationTemplate


@dataclass(frozen=True)
class NotificationsRenderer(ABC):
    @abstractmethod
    def render_preview(
        self,
        template: NotificationTemplate,
        variables: dict[str, Any],
    ) -> NotificationPreview:
        raise NotImplementedError
