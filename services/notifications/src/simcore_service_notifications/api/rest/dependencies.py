"""Free functions to inject dependencies in routes handlers"""

from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from servicelib.rabbitmq import RabbitMQRPCClient

from ...clients.postgres import PostgresLiveness
from ...clients.postgres import get_postgres_liveness as _get_db_liveness
from ...renderers.jinja_notifications_renderer import JinjaNotificationsRenderer
from ...renderers.notifications_renderer import NotificationsRenderer
from ...repository.filesystem_notifications_templates_repository import FilesystemNotificationsTemplatesRepository
from ...repository.notifications_templates_repository import NotificationsTemplatesRepository
from ...services.notifications_templates_service import NotificationsTemplatesService


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


def get_notifications_templates_renderer() -> NotificationsRenderer:
    return JinjaNotificationsRenderer()


def get_notifications_templates_repository() -> NotificationsTemplatesRepository:
    return FilesystemNotificationsTemplatesRepository()


def get_notifications_templates_service(
    repository: Annotated[NotificationsTemplatesRepository, Depends(get_notifications_templates_repository)],
    renderer: Annotated[NotificationsRenderer, Depends(get_notifications_templates_renderer)],
) -> NotificationsTemplatesService:
    return NotificationsTemplatesService(repository, renderer)
