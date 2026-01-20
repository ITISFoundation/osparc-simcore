from typing import Protocol

from jinja2 import Environment


class NotificationsTemplatesRepository(Protocol):
    def get_jinja_environment(self) -> Environment: ...

    def template_path(self, template_name: str, channel_name: str) -> str: ...
