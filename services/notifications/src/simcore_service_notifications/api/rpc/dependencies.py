from fastapi import FastAPI
from jinja2 import Environment
from notifications_library._render import create_render_environment_from_notifications_library
from servicelib.celery.task_manager import TaskManager

from ...renderers import JinjaRenderer, Renderer
from ...repositories import FileTemplateRepository, TemplateRepository
from ...services import MessagesService, TemplateService


def get_jinja_env() -> Environment:
    return create_render_environment_from_notifications_library()


def get_template_repository() -> TemplateRepository:
    return FileTemplateRepository(get_jinja_env())


def get_renderer() -> Renderer:
    return JinjaRenderer(get_template_repository())


def get_template_service() -> TemplateService:
    return TemplateService(get_template_repository(), get_renderer())


def get_messages_service(app: FastAPI) -> MessagesService:
    task_manager: TaskManager = app.state.task_manager
    return MessagesService(task_manager=task_manager)
