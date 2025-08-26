import contextlib
from collections.abc import AsyncIterator

import socketio  # type: ignore[import-untyped]
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi_lifespan_manager import State
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.socketio import (
    SOCKET_IO_SERVICE_STATUS_EVENT,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.projects import ProjectID
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.services_utils import get_status_as_dict


class Notifier(SingletonInAppStateMixin):
    app_state_name: str = "notifier"

    def __init__(self, sio_manager: socketio.AsyncAioPikaManager):
        self._sio_manager = sio_manager

    async def notify_service_status(
        self, project_id: ProjectID, status: NodeGet | DynamicServiceGet | NodeGetIdle
    ) -> None:
        await self._sio_manager.emit(
            SOCKET_IO_SERVICE_STATUS_EVENT,
            data=jsonable_encoder(get_status_as_dict(status)),
            room=SocketIORoomStr.from_project_id(project_id),
        )


async def notify_service_status_change(
    app: FastAPI,
    project_id: ProjectID,
    status: NodeGet | DynamicServiceGet | NodeGetIdle,
) -> None:
    notifier: Notifier = Notifier.get_from_app_state(app)
    await notifier.notify_service_status(project_id=project_id, status=status)


async def lifespan(app: FastAPI) -> AsyncIterator[State]:

    assert app.state.external_socketio  # nosec

    notifier = Notifier(
        sio_manager=app.state.external_socketio,
    )
    notifier.set_to_app_state(app)
    assert Notifier.get_from_app_state(app) == notifier  # nosec

    yield {}

    with contextlib.suppress(AttributeError):
        Notifier.pop_from_app_state(app)
