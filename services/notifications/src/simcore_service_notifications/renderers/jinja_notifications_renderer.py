from dataclasses import dataclass
from typing import Any

from jinja2 import Environment


@dataclass(frozen=True)
class JinjaNotificationsRenderer:
    def render(self, template_path: str, env: Environment, variables: dict[str, Any]) -> str:
        template = env.get_template(template_path)
        return template.render(variables)
