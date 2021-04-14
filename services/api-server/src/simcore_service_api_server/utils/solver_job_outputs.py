import logging
from typing import Dict, Union

import aiopg
from fastapi import status
from fastapi.exceptions import HTTPException
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import BaseFileLink
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports.dbmanager import DBManager
from simcore_sdk.node_ports_v2 import Nodeports

from .typing_extra import get_args

log = logging.getLogger(__name__)


ResultsTypes = Union[float, int, bool, BaseFileLink, str, None]


async def get_solver_output_results(
    user_id: int, project_uuid: ProjectID, node_uuid: NodeID, db_engine: aiopg.sa.Engine
) -> Dict[str, ResultsTypes]:
    """
    Wraps calls via node_ports to retrieve project's output
    """

    node_ports_v2.node_config.USER_ID = str(user_id)
    node_ports_v2.node_config.PROJECT_ID = str(project_uuid)
    node_ports_v2.node_config.NODE_UUID = str(node_uuid)

    # get the DB engine
    db_manager = DBManager(db_engine=db_engine)

    try:
        solver: Nodeports = await node_ports_v2.ports(db_manager)
        solver_output_results = {}
        for port in (await solver.outputs).values():
            log.debug("Getting %s [%s]: %s", port.key, port.property_type, port.value)
            assert port.value in get_args(ResultsTypes)  # nosec
            solver_output_results[port.key] = port.value

        return solver_output_results

    except node_ports_v2.exceptions.NodeNotFound as err:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Solver {node_uuid} output of project {project_uuid} not found",
        ) from err
