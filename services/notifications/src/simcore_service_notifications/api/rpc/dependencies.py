from jinja2 import Environment
from notifications_library._render import create_render_environment_from_notifications_library

from simcore_service_notifications.services._messages_service import MessagesService

from ...renderers import JinjaNotificationsRenderer
from ...repositories import FileTemplatesRepository
from ...services import TemplatesService


def get_jinja_env() -> Environment:
    return create_render_environment_from_notifications_library()


def get_templates_service() -> TemplatesService:
    env = get_jinja_env()
    templates_repo = FileTemplatesRepository(env)
    renderer = JinjaNotificationsRenderer(templates_repo)
    return TemplatesService(templates_repo, renderer)


def get_messages_service(templates_service: TemplatesService | None = None) -> MessagesService:
    templates_service = templates_service or get_templates_service()
    return MessagesService(templates_service)
