from pathlib import Path

from fastapi import FastAPI
from models_library.api_schemas_dynamic_sidecar.telemetry import DiskUsage
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID

from ._notifier import Notifier


async def publish_disk_usage(
    app: FastAPI, *, user_id: UserID, node_id: NodeID, usage: dict[Path, DiskUsage]
) -> None:
    notifier: Notifier = Notifier.get_from_app_state(app)
    await notifier.notify_service_disk_usage(
        user_id=user_id, node_id=node_id, usage=usage
    )
