import contextlib

import socketio  # type: ignore[import-untyped]
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_dynamic_sidecar.ports import (
    InputPortStatus,
    InputStatus,
    OutputPortStatus,
    OutputStatus,
)
from models_library.api_schemas_dynamic_sidecar.socketio import (
    SOCKET_IO_SERVICE_DISK_USAGE_EVENT,
    SOCKET_IO_STATE_INPUT_PORTS_EVENT,
    SOCKET_IO_STATE_OUTPUT_PORTS_EVENT,
)
from models_library.api_schemas_dynamic_sidecar.telemetry import (
    DiskUsage,
    MountPathCategory,
    ServiceDiskUsage,
)
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServicePortKey
from models_library.users import UserID
from servicelib.fastapi.app_state import SingletonInAppStateMixin


class Notifier(SingletonInAppStateMixin):
    app_state_name: str = "notifier"

    def __init__(self, sio_manager: socketio.AsyncAioPikaManager):
        self._sio_manager = sio_manager

    async def notify_service_disk_usage(
        self,
        user_id: UserID,
        node_id: NodeID,
        usage: dict[MountPathCategory, DiskUsage],
    ) -> None:
        await self._sio_manager.emit(
            SOCKET_IO_SERVICE_DISK_USAGE_EVENT,
            data=jsonable_encoder(ServiceDiskUsage(node_id=node_id, usage=usage)),
            room=SocketIORoomStr.from_user_id(user_id),
        )

    async def notify_output_port_status(
        self,
        user_id: UserID,
        project_id: ProjectID,
        node_id: NodeID,
        port_key: ServicePortKey,
        output_status: OutputStatus,
    ) -> None:
        await self._sio_manager.emit(
            SOCKET_IO_STATE_OUTPUT_PORTS_EVENT,
            data=jsonable_encoder(
                OutputPortStatus(
                    project_id=project_id,
                    node_id=node_id,
                    port_key=port_key,
                    status=output_status,
                )
            ),
            room=SocketIORoomStr.from_user_id(user_id),
        )

    async def notify_input_port_status(
        self,
        user_id: UserID,
        project_id: ProjectID,
        node_id: NodeID,
        port_key: ServicePortKey,
        input_status: InputStatus,
    ) -> None:
        await self._sio_manager.emit(
            SOCKET_IO_STATE_INPUT_PORTS_EVENT,
            data=jsonable_encoder(
                InputPortStatus(
                    project_id=project_id,
                    node_id=node_id,
                    port_key=port_key,
                    status=input_status,
                )
            ),
            room=SocketIORoomStr.from_user_id(user_id),
        )


def setup_notifier(app: FastAPI):
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
