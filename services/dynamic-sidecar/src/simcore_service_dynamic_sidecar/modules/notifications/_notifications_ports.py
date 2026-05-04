from dataclasses import dataclass

from fastapi import FastAPI
from models_library.api_schemas_dynamic_sidecar.ports import InputStatus, OutputStatus
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServicePortKey
from models_library.users import UserID

from ._notifier import Notifier


@dataclass
class PortNotifier:
    app: FastAPI
    user_id: UserID
    project_id: ProjectID
    node_id: NodeID

    async def _send_output_port_status(self, port_key: ServicePortKey, status: OutputStatus) -> None:
        notifier: Notifier = Notifier.get_from_app_state(self.app)
        await notifier.notify_output_port_status(self.user_id, self.project_id, self.node_id, port_key, status)

    async def _send_input_port_status(self, port_key: ServicePortKey, status: InputStatus) -> None:
        notifier: Notifier = Notifier.get_from_app_state(self.app)
        await notifier.notify_input_port_status(self.user_id, self.project_id, self.node_id, port_key, status)

    async def send_output_port_upload_started(self, port_key: ServicePortKey) -> None:
        await self._send_output_port_status(port_key, OutputStatus.UPLOAD_STARTED)

    async def send_output_port_upload_was_aborted(self, port_key: ServicePortKey) -> None:
        await self._send_output_port_status(port_key, OutputStatus.UPLOAD_WAS_ABORTED)

    async def send_output_port_upload_finished_successfully(self, port_key: ServicePortKey) -> None:
        await self._send_output_port_status(port_key, OutputStatus.UPLOAD_FINISHED_SUCCESSFULLY)

    async def send_output_port_upload_finished_with_error(self, port_key: ServicePortKey) -> None:
        await self._send_output_port_status(port_key, OutputStatus.UPLOAD_FINISHED_WITH_ERROR)

    async def send_input_port_download_started(self, port_key: ServicePortKey) -> None:
        await self._send_input_port_status(port_key, InputStatus.DOWNLOAD_STARTED)

    async def send_input_port_download_was_aborted(self, port_key: ServicePortKey) -> None:
        await self._send_input_port_status(port_key, InputStatus.DOWNLOAD_WAS_ABORTED)

    async def send_input_port_download_finished_successfully(self, port_key: ServicePortKey) -> None:
        await self._send_input_port_status(port_key, InputStatus.DOWNLOAD_FINISHED_SUCCESSFULLY)

    async def send_input_port_download_finished_with_error(self, port_key: ServicePortKey) -> None:
        await self._send_input_port_status(port_key, InputStatus.DOWNLOAD_FINISHED_WITH_ERROR)
