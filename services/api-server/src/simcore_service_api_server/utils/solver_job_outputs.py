import logging
from typing import TypeAlias

import aiopg
from fastapi import status
from fastapi.exceptions import HTTPException
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import BaseFileLink
from pydantic import StrictBool, StrictFloat, StrictInt, parse_obj_as
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports_v2 import DBManager, Nodeports

log = logging.getLogger(__name__)

# ResultsTypes are types used in the job outputs (see ArgumentType)
ResultsTypes: TypeAlias = (
    StrictFloat | StrictInt | StrictBool | BaseFileLink | str | list | None
)


async def get_solver_output_results(
    user_id: int, project_uuid: ProjectID, node_uuid: NodeID, db_engine: aiopg.sa.Engine
) -> dict[str, ResultsTypes]:
    """
    Wraps calls via node_ports to retrieve project's output
    """

    # get the DB engine
    db_manager = DBManager(db_engine=db_engine)

    try:
        solver: Nodeports = await node_ports_v2.ports(
            user_id=user_id,
            project_id=f"{project_uuid}",
            node_uuid=f"{node_uuid}",
            db_manager=db_manager,
        )
        solver_output_results = {}
        for port in (await solver.outputs).values():
            log.debug("Getting %s [%s]: %s", port.key, port.property_type, port.value)
            assert parse_obj_as(ResultsTypes, port.value) == port.value  # type: ignore  # nosec
            solver_output_results[port.key] = port.value

        return solver_output_results

    except node_ports_v2.exceptions.NodeNotFound as err:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Solver {node_uuid} output of project {project_uuid} not found",
        ) from err
