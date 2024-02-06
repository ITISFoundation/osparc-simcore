import contextlib
import logging

import socketio
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_directorv2.dynamic_services_utils import (
    get_service_status_serialization_options,
)
from models_library.api_schemas_dynamic_scheduler.socketio import (
    SOCKET_IO_SERVICE_STATUS_EVENT,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from servicelib.fastapi.app_state import SingletonInAppStateMixin

_logger = logging.getLogger(__name__)


class Notifier(SingletonInAppStateMixin):
    app_state_name: str = "notifier"

    def __init__(self, sio_manager: socketio.AsyncAioPikaManager):
        self._sio_manager = sio_manager

    async def notify_service_status(
        self,
        user_id: UserID,
        service_status: NodeGet | DynamicServiceGet | NodeGetIdle,
    ) -> None:
        await self._sio_manager.emit(
            SOCKET_IO_SERVICE_STATUS_EVENT,
            data=jsonable_encoder(
                service_status,
                **get_service_status_serialization_options(service_status),
            ),
            room=SocketIORoomStr.from_user_id(user_id),
        )


async def publish_message(
    app: FastAPI,
    *,
    node_id: NodeID,
    service_status: NodeGet | DynamicServiceGet | NodeGetIdle,
    user_id: UserID,
) -> None:
    _logger.debug(
        "Publishing message for service %s and user_id %s -> %s",
        node_id,
        user_id,
        service_status,
    )
    notifier: Notifier = Notifier.get_from_app_state(app)
    await notifier.notify_service_status(
        user_id=user_id,
        service_status=service_status,
    )


def setup_core(app: FastAPI):
    async def _on_startup() -> None:
        assert app.state.external_socketio  # nosec

        notifier = Notifier(
            sio_manager=app.state.external_socketio,
        )
        notifier.set_to_app_state(app)
        assert Notifier.get_from_app_state(app) == notifier  # nosec

    async def _on_shutdown() -> None:
        with contextlib.suppress(AttributeError):
            Notifier.pop_from_app_state(app)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
