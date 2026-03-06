from fastapi import FastAPI
from jinja2 import Environment
from notifications_library._render import create_render_environment_from_notifications_library

from ...modules.postgres import get_repository
from ...renderers import JinjaNotificationsRenderer
from ...repositories import FileTemplatesRepository, UserPreferencesRepository
from ...services import TemplatesService, UserPreferencesService


def get_jinja_env() -> Environment:
    return create_render_environment_from_notifications_library()


def get_notifications_templates_service() -> TemplatesService:
    env = get_jinja_env()
    templates_repo = FileTemplatesRepository(env)
    renderer = JinjaNotificationsRenderer(templates_repo)
    return TemplatesService(templates_repo, renderer)


def get_user_preferences_service(app: FastAPI) -> UserPreferencesService:
    return UserPreferencesService(get_repository(app, UserPreferencesRepository))
