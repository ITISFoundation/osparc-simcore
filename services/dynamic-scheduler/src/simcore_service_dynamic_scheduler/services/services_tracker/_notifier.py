import logging

from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from models_library.users import GroupID

_logger = logging.getLogger(__name__)


async def publish_message(
    app: FastAPI,
    *,
    node_id: NodeID,
    service_status: NodeGet | DynamicServiceGet | NodeGetIdle,
    primary_group_id: GroupID
) -> None:
    _ = app
    _logger.debug(
        "Publishing message for %s(%s) -> %s", node_id, primary_group_id, service_status
    )
    # NOTE: implementation is coming in a followup PR
