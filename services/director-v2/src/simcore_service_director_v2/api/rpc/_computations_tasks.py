from pathlib import Path

from fastapi import FastAPI
from models_library.api_schemas_directorv2.computations import TaskLogFileIdGet
from models_library.api_schemas_directorv2.errors import ComputationalTaskMissingError
from models_library.projects import ProjectID
from servicelib.rabbitmq import RPCRouter
from simcore_sdk.node_ports_common import data_items_utils

from ...core.errors import PipelineNotFoundError
from ...modules.db.repositories.comp_pipelines import CompPipelinesRepository
from ...modules.db.repositories.comp_tasks import CompTasksRepository
from ...utils import dask as dask_utils
from ...utils.computations_tasks import get_pipeline_info

router = RPCRouter()


@router.expose(reraise_if_error_type=(ComputationalTaskMissingError,))
async def get_computation_task_log_file_ids(
    app: FastAPI,
    project_id: ProjectID,
) -> list[TaskLogFileIdGet]:
    comp_pipelines_repo = CompPipelinesRepository.instance(db_engine=app.state.engine)
    comp_tasks_repo = CompTasksRepository.instance(db_engine=app.state.engine)

    try:
        info = await get_pipeline_info(
            project_id=project_id,
            comp_pipelines_repo=comp_pipelines_repo,
            comp_tasks_repo=comp_tasks_repo,
        )
    except PipelineNotFoundError as exc:
        raise ComputationalTaskMissingError(project_id=project_id) from exc

    iter_task_ids = (t.node_id for t in info.filtered_tasks)

    return [
        TaskLogFileIdGet(
            task_id=node_id,
            file_id=data_items_utils.create_simcore_file_id(
                Path(dask_utils.LOGS_FILE_NAME), f"{project_id}", f"{node_id}"
            ),
        )
        for node_id in iter_task_ids
    ]
