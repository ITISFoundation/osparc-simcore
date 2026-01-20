from dataclasses import dataclass
from typing import Any

from ..renderers.notifications_renderer import NotificationsRenderer
from ..repository import NotificationsTemplatesRepository


@dataclass(frozen=True)
class NotificationsTemplatesService:
    repository: NotificationsTemplatesRepository
    renderer: NotificationsRenderer

    def preview_template(self, template_name: str, channel_name: str, variables: dict[str, Any]) -> str:
        return self.renderer.render(
            env=self.repository.get_jinja_environment(),
            template_path=self.repository.template_path(template_name, channel_name),
            variables=variables,
        )
