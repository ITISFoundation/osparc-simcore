from jinja2 import Environment
from notifications_library._render import create_render_environment_from_notifications_library

from ...renderers import JinjaNotificationsRenderer
from ...repositories import FileTemplatesRepository
from ...services import TemplatesService


def get_jinja_env() -> Environment:
    return create_render_environment_from_notifications_library()


def get_notifications_templates_service() -> TemplatesService:
    env = get_jinja_env()
    templates_repo = FileTemplatesRepository(env)
    renderer = JinjaNotificationsRenderer(templates_repo)
    return TemplatesService(templates_repo, renderer)
