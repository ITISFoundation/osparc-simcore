from fastapi import FastAPI
from jinja2 import Environment
from notifications_library._render import create_render_environment_from_notifications_library

from ...clients.celery import get_task_manager
from ...core.settings import ApplicationSettings
from ...renderers import JinjaRenderer, Renderer
from ...repositories import FileTemplateRepository, TemplateRepository
from ...services import MessageService, TemplateService


def get_jinja_env() -> Environment:
    return create_render_environment_from_notifications_library()


def get_template_repository(env: Environment | None = None) -> TemplateRepository:
    return FileTemplateRepository(env if env is not None else get_jinja_env())


def get_renderer(template_repository: TemplateRepository | None = None) -> Renderer:
    return JinjaRenderer(template_repository if template_repository is not None else get_template_repository())


def get_template_service(
    template_repository: TemplateRepository | None = None,
    renderer: Renderer | None = None,
) -> TemplateService:
    repo = template_repository if template_repository is not None else get_template_repository()
    rend = renderer if renderer is not None else get_renderer(repo)
    return TemplateService(repo, rend)


def get_message_service(
    app: FastAPI,
    template_service: TemplateService | None = None,
) -> MessageService:
    settings: ApplicationSettings = app.state.settings

    return MessageService(
        template_service if template_service is not None else get_template_service(),
        get_task_manager(app),
        settings,
    )
