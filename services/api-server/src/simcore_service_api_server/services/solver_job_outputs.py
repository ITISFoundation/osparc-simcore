import logging
from typing import Any, TypeAlias

import aiopg
from models_library.projects import ProjectID, ProjectIDStr
from models_library.projects_nodes_io import BaseFileLink, NodeID, NodeIDStr
from pydantic import StrictBool, StrictFloat, StrictInt, TypeAdapter
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports_v2 import DBManager, Nodeports
from simcore_service_api_server.exceptions.backend_errors import (
    SolverOutputNotFoundError,
)

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
            project_id=ProjectIDStr(f"{project_uuid}"),
            node_uuid=NodeIDStr(f"{node_uuid}"),
            db_manager=db_manager,
        )
        solver_output_results: dict[str, Any] = {}
        for port in (await solver.outputs).values():
            log.debug(
                "Output %s [%s]: %s",
                port.key,
                port.property_type,
                port.value,
            )
            assert TypeAdapter(ResultsTypes).validate_python(port.value) == port.value  # type: ignore  # nosec

            solver_output_results[port.key] = port.value

        return solver_output_results

    except node_ports_v2.exceptions.NodeNotFound as err:
        raise SolverOutputNotFoundError(project_uuid=project_uuid) from err
