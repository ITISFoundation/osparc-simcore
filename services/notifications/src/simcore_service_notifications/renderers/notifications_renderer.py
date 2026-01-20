from typing import Any, Protocol

from jinja2 import Environment


class NotificationsRenderer(Protocol):
    def render(self, template_path: str, env: Environment, variables: dict[str, Any]) -> str: ...
