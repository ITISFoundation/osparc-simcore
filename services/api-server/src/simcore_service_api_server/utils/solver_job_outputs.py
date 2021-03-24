import logging
from pathlib import Path

import aiopg
from fastapi import status
from fastapi.exceptions import HTTPException
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import BaseFileLink
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports.dbmanager import DBManager

from ..models.schemas.files import File
from ..models.schemas.jobs import KeywordArguments

log = logging.getLogger(__name__)


async def get_solver_output_results(
    user_id: int, project_uuid: ProjectID, node_uuid: NodeID, db_engine: aiopg.sa.Engine
) -> KeywordArguments:
    node_ports_v2.node_config.USER_ID = str(user_id)
    node_ports_v2.node_config.PROJECT_ID = str(project_uuid)
    node_ports_v2.node_config.NODE_UUID = str(node_uuid)

    # get the DB engine
    db_manager = DBManager(db_engine=db_engine)
    try:
        PORTS = await node_ports_v2.ports(db_manager)
        solver_output_results = {}
        for port in (await PORTS.outputs).values():
            log.debug(
                "PROCESSING %s [%s]: %s", port.key, port.property_type, port.value
            )
            solver_output_results[port.key] = port.value
            if isinstance(port.value, BaseFileLink):
                file_link: BaseFileLink = port.value
                solver_output_results[port.key] = await File.create_from_file_link(
                    file_link.path, file_link.e_tag
                )
        return solver_output_results

    except node_ports_v2.exceptions.NodeNotFound as err:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Solver {node_uuid} output of project {project_uuid} not found",
        ) from err
