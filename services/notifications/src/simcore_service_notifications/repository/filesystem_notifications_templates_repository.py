import logging
from dataclasses import dataclass

from jinja2 import Environment
from notifications_library._render import create_render_environment_from_notifications_library

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FilesystemNotificationsTemplatesRepository:
    def get_jinja_environment(self) -> Environment:
        return create_render_environment_from_notifications_library()

    def template_path(self, template_name: str, channel_name: str) -> str:
        return f"{template_name}.{channel_name}.content.html"
