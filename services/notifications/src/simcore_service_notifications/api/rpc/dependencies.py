from jinja2 import Environment
from notifications_library._render import create_render_environment_from_notifications_library

from ...renderers.jinja_renderer import JinjaNotificationsRenderer
from ...repository import FileTemplatesRepository
from ...services.templates_service import TemplatesService


def get_jinja_env() -> Environment:
    return create_render_environment_from_notifications_library()


def get_notifications_templates_service() -> TemplatesService:
    env = get_jinja_env()
    repository = FileTemplatesRepository(env)
    renderer = JinjaNotificationsRenderer(repository)
    return TemplatesService(repository, renderer)
