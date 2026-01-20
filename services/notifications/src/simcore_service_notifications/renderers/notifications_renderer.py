from typing import Any, Protocol

from jinja2 import Environment


class NotificationsRenderer(Protocol):
    def render(self, env: Environment, template_path: str, variables: dict[str, Any]) -> str: ...
