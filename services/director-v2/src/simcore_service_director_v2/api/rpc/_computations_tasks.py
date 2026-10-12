from pathlib import Path

from fastapi import FastAPI
from models_library.api_schemas_directorv2.computations import TaskLogFileIdGet
from models_library.projects import ProjectID
from servicelib.fastapi.db_asyncpg_engine import get_engine
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.director_v2.errors import (
    ComputationalTaskMissingError,
)
from simcore_sdk.node_ports_common import data_items_utils

from ...constants import LOGS_FILE_NAME
from ...core.errors import PipelineNotFoundError, PipelineTaskMissingError
from ...utils.computations_tasks import validate_pipeline

router = RPCRouter()


@router.expose(reraise_if_error_type=(ComputationalTaskMissingError,))
async def get_computation_task_log_file_ids(
    app: FastAPI,
    project_id: ProjectID,
) -> list[TaskLogFileIdGet]:
    try:
        info = await validate_pipeline(
            get_engine(app),
            project_id=project_id,
        )
    except (PipelineNotFoundError, PipelineTaskMissingError) as exc:
        raise ComputationalTaskMissingError(project_id=project_id) from exc

    iter_task_ids = (t.node_id for t in info.filtered_tasks)

    return [
        TaskLogFileIdGet(
            task_id=node_id,
            file_id=data_items_utils.create_simcore_file_id(Path(LOGS_FILE_NAME), f"{project_id}", f"{node_id}"),
        )
        for node_id in iter_task_ids
    ]
