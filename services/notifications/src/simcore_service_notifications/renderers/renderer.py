from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..models.preview import NotificationPreview
from ..models.template import NotificationTemplate
from ..template.content.models import NotificationContent


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
