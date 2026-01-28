from jinja2 import Environment
from notifications_library._render import create_render_environment_from_notifications_library

from ...renderers.jinja_renderer import JinjaNotificationsRenderer
from ...repository.templates_repository import NotificationsTemplatesRepository
from ...services.templates_service import NotificationsTemplatesService


def get_jinja_env() -> Environment:
    return create_render_environment_from_notifications_library()


def get_notifications_templates_service() -> NotificationsTemplatesService:
    env = get_jinja_env()
    repository = NotificationsTemplatesRepository(env)
    renderer = JinjaNotificationsRenderer(repository)
    return NotificationsTemplatesService(repository, renderer)
