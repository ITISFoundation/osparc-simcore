from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..content.models import NotificationContent
from ..models.preview import NotificationPreview
from ..models.template import NotificationTemplate


@dataclass(frozen=True)
class NotificationsRenderer(ABC):
    content_cls_registry: dict[str, type[NotificationContent]]

    @abstractmethod
    def render_preview(
        self,
        template: NotificationTemplate,
        variables: dict[str, Any],
    ) -> NotificationPreview:
        raise NotImplementedError
