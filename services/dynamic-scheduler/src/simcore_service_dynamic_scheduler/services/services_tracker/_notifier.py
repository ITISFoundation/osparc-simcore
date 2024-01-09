# use the Notifer pattern used in payments as PC pointed out
# requires the user_id to properly target for the status


# NOTE: messages will be sent to all the open tabs, they need to be filtered by the fronted
# in order to figure out if they require to update the project. should also include project_id
# to be sure about all the possible issues


import logging

from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID

_logger = logging.getLogger(__name__)


async def publish_message(
    app: FastAPI,
    *,
    node_id: NodeID,
    service_status: NodeGet | DynamicServiceGet | NodeGetIdle
) -> None:
    _ = app
    _logger.debug("Publishing message for %s -> %s", node_id, service_status)
    # TODO: finish here
