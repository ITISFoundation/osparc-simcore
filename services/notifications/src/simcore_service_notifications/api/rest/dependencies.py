# pylint:disable=unused-import

from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from jinja2 import Environment
from notifications_library._render import create_render_environment_from_notifications_library
from servicelib.rabbitmq import RabbitMQRPCClient

from ...clients.postgres import PostgresLiveness
from ...clients.postgres import get_postgres_liveness as _get_db_liveness
from ...models.content import EmailNotificationContent, NotificationContent, SMSNotificationContent
from ...renderers.jinja_renderer import JinjaNotificationsRenderer
from ...renderers.renderer import NotificationsRenderer
from ...repository.templates_repository import NotificationsTemplatesRepository
from ...services.templates_service import NotificationsTemplatesService
from ...variables import models  # noqa: F401 # NOTE: registers variables models


def get_application(request: Request) -> FastAPI:
    return cast(FastAPI, request.app)


def get_rabbitmq_client(
    app: Annotated[FastAPI, Depends(get_application)],
) -> RabbitMQRPCClient:
    assert isinstance(app.state.rabbitmq_rpc_server, RabbitMQRPCClient)  # nosec
    return app.state.rabbitmq_rpc_server


def get_postgres_liveness(
    app: Annotated[FastAPI, Depends(get_application)],
) -> PostgresLiveness:
    return _get_db_liveness(app)


def get_jinja_env() -> Environment:
    return create_render_environment_from_notifications_library()


def get_notifications_content_cls_registry() -> dict[str, type[NotificationContent]]:
    return {
        "email": EmailNotificationContent,
        "sms": SMSNotificationContent,
    }


def get_notifications_templates_repository(
    env: Annotated[Environment, Depends(get_jinja_env)],
) -> NotificationsTemplatesRepository:
    return NotificationsTemplatesRepository(env)


def get_notifications_templates_renderer(
    repository: Annotated[NotificationsTemplatesRepository, Depends(get_notifications_templates_repository)],
    content_cls_registry: Annotated[
        dict[str, type[NotificationContent]], Depends(get_notifications_content_cls_registry)
    ],
) -> NotificationsRenderer:
    return JinjaNotificationsRenderer(content_cls_registry, repository)


def get_notifications_templates_service(
    repository: Annotated[NotificationsTemplatesRepository, Depends(get_notifications_templates_repository)],
    renderer: Annotated[NotificationsRenderer, Depends(get_notifications_templates_renderer)],
) -> NotificationsTemplatesService:
    return NotificationsTemplatesService(repository, renderer)
