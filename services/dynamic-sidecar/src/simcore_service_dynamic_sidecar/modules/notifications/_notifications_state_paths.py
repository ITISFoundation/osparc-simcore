from dataclasses import dataclass

from fastapi import FastAPI
from models_library.api_schemas_dynamic_sidecar.state_paths import MountActivityStatus
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID

from ._notifier import Notifier


@dataclass
class StatePathsNotifier:
    app: FastAPI
    user_id: UserID
    project_id: ProjectID
    node_id: NodeID

    async def send_state_paths_status(self, status: MountActivityStatus) -> None:
        notifier: Notifier = Notifier.get_from_app_state(self.app)
        await notifier.notify_state_paths_status(self.user_id, self.project_id, self.node_id, status)
