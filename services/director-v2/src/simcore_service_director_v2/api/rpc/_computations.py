# pylint: disable=too-many-arguments
from fastapi import FastAPI
from models_library.api_schemas_directorv2.comp_runs import (
    ComputationRunRpcGetPage,
    ComputationTaskRpcGet,
    ComputationTaskRpcGetPage,
)
from models_library.api_schemas_directorv2.computations import TaskLogFileGet
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from servicelib.rabbitmq import RPCRouter
from servicelib.utils import limited_gather
from simcore_service_director_v2.models.comp_tasks import ComputationTaskForRpcDBGet

from ...modules.db.repositories.comp_runs import CompRunsRepository
from ...modules.db.repositories.comp_tasks import CompTasksRepository
from ...utils import dask as dask_utils

router = RPCRouter()


@router.expose(reraise_if_error_type=())
async def list_computations_latest_iteration_page(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    # filters
    filter_only_running: bool = False,
    # pagination
    offset: int = 0,
    limit: int = 20,
    # ordering
    order_by: OrderBy | None = None,
) -> ComputationRunRpcGetPage:
    comp_runs_repo = CompRunsRepository.instance(db_engine=app.state.engine)
    total, comp_runs_output = (
        await comp_runs_repo.list_for_user__only_latest_iterations(
            product_name=product_name,
            user_id=user_id,
            filter_only_running=filter_only_running,
            offset=offset,
            limit=limit,
            order_by=order_by,
        )
    )
    return ComputationRunRpcGetPage(
        items=comp_runs_output,
        total=total,
    )


@router.expose(reraise_if_error_type=())
async def list_computations_iterations_page(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    # pagination
    offset: int = 0,
    limit: int = 20,
    # ordering
    order_by: OrderBy | None = None,
) -> ComputationRunRpcGetPage:
    comp_runs_repo = CompRunsRepository.instance(db_engine=app.state.engine)
    total, comp_runs_output = (
        await comp_runs_repo.list_for_user_and_project_all_iterations(
            product_name=product_name,
            user_id=user_id,
            project_id=project_id,
            offset=offset,
            limit=limit,
            order_by=order_by,
        )
    )
    return ComputationRunRpcGetPage(
        items=comp_runs_output,
        total=total,
    )


async def _fetch_task_log(
    user_id: UserID, project_id: ProjectID, task: ComputationTaskForRpcDBGet
) -> TaskLogFileGet | None:
    if not task.state.is_running():
        return await dask_utils.get_task_log_file(
            user_id=user_id,
            project_id=project_id,
            node_id=task.node_id,
        )
    return None


@router.expose(reraise_if_error_type=())
async def list_computations_latest_iteration_tasks_page(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    # pagination
    offset: int = 0,
    limit: int = 20,
    # ordering
    order_by: OrderBy | None = None,
) -> ComputationTaskRpcGetPage:
    assert product_name  # nosec  NOTE: Whether project_id belong to the product_name was checked in the webserver
    assert user_id  # nosec  NOTE: Whether user_id has access to the project was checked in the webserver

    comp_tasks_repo = CompTasksRepository.instance(db_engine=app.state.engine)
    comp_runs_repo = CompRunsRepository.instance(db_engine=app.state.engine)

    comp_latest_run = await comp_runs_repo.get(
        user_id=user_id, project_id=project_id, iteration=None  # Returns last iteration
    )

    total, comp_tasks = await comp_tasks_repo.list_computational_tasks_rpc_domain(
        project_id=project_id,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )

    # Run all log fetches concurrently
    log_files = await limited_gather(
        *[_fetch_task_log(user_id, project_id, task) for task in comp_tasks],
        limit=20,
    )

    comp_tasks_output = [
        ComputationTaskRpcGet(
            project_uuid=task.project_uuid,
            node_id=task.node_id,
            state=task.state,
            progress=task.progress,
            image=task.image,
            started_at=task.started_at,
            ended_at=task.ended_at,
            log_download_link=log_file.download_link if log_file else None,
            service_run_id=ServiceRunID.get_resource_tracking_run_id_for_computational(
                user_id, project_id, task.node_id, comp_latest_run.iteration
            ),
        )
        for task, log_file in zip(comp_tasks, log_files, strict=True)
    ]

    return ComputationTaskRpcGetPage(
        items=comp_tasks_output,
        total=total,
    )
