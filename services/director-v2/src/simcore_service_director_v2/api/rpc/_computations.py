# pylint: disable=too-many-arguments
from fastapi import FastAPI
from models_library.api_schemas_directorv2.comp_runs import (
    ComputationCollectionRunRpcGetPage,
    ComputationCollectionRunTaskRpcGet,
    ComputationCollectionRunTaskRpcGetPage,
    ComputationRunRpcGetPage,
    ComputationTaskRpcGet,
    ComputationTaskRpcGetPage,
)
from models_library.api_schemas_directorv2.computations import TaskLogFileGet
from models_library.computations import CollectionRunID
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from servicelib.rabbitmq import RPCRouter
from servicelib.utils import limited_gather

from ...core.errors import ComputationalRunNotFoundError
from ...models.comp_run_snapshot_tasks import (
    CompRunSnapshotTaskDBGet,
)
from ...models.comp_runs import CompRunsAtDB
from ...models.comp_tasks import ComputationTaskForRpcDBGet
from ...modules.db.repositories.comp_runs import CompRunsRepository
from ...modules.db.repositories.comp_runs_snapshot_tasks import (
    CompRunsSnapshotTasksRepository,
)
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
    project_ids: list[ProjectID],
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
            project_ids=project_ids,
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
async def list_computation_collection_runs_page(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_ids: list[ProjectID] | None,
    filter_only_running: bool = False,
    # pagination
    offset: int = 0,
    limit: int = 20,
) -> ComputationCollectionRunRpcGetPage:
    comp_runs_repo = CompRunsRepository.instance(db_engine=app.state.engine)

    collection_run_ids: list[CollectionRunID] | None = None
    if filter_only_running is True:
        collection_run_ids = await comp_runs_repo.list_all_collection_run_ids_for_user_currently_running_computations(
            product_name=product_name, user_id=user_id
        )
        if collection_run_ids == []:
            return ComputationCollectionRunRpcGetPage(items=[], total=0)

    total, comp_runs_output = await comp_runs_repo.list_group_by_collection_run_id(
        product_name=product_name,
        user_id=user_id,
        project_ids_or_none=project_ids,
        collection_run_ids_or_none=collection_run_ids,
        offset=offset,
        limit=limit,
    )
    return ComputationCollectionRunRpcGetPage(
        items=comp_runs_output,
        total=total,
    )


async def _fetch_task_log(
    user_id: UserID, task: CompRunSnapshotTaskDBGet | ComputationTaskForRpcDBGet
) -> TaskLogFileGet | None:
    if not task.state.is_running():
        return await dask_utils.get_task_log_file(
            user_id=user_id,
            project_id=task.project_uuid,
            node_id=task.node_id,
        )
    return None


async def _get_latest_run_or_none(
    comp_runs_repo: CompRunsRepository,
    user_id: UserID,
    project_uuid: ProjectID,
) -> CompRunsAtDB | None:
    try:
        return await comp_runs_repo.get(
            user_id=user_id, project_id=project_uuid, iteration=None
        )
    except ComputationalRunNotFoundError:
        return None


@router.expose(reraise_if_error_type=())
async def list_computations_latest_iteration_tasks_page(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_ids: list[ProjectID],
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

    total, comp_tasks = await comp_tasks_repo.list_computational_tasks_rpc_domain(
        project_ids=project_ids,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )

    # Get unique set of all project_uuids from comp_tasks
    unique_project_uuids = {task.project_uuid for task in comp_tasks}

    # Fetch latest run for each project concurrently
    latest_runs = await limited_gather(
        *[
            _get_latest_run_or_none(comp_runs_repo, user_id, project_uuid)
            for project_uuid in unique_project_uuids
        ],
        limit=20,
    )
    # Build a dict: project_uuid -> iteration
    project_uuid_to_iteration = {
        run.project_uuid: run.iteration for run in latest_runs if run is not None
    }

    # Run all log fetches concurrently
    log_files = await limited_gather(
        *[_fetch_task_log(user_id, task) for task in comp_tasks],
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
                user_id,
                task.project_uuid,
                task.node_id,
                project_uuid_to_iteration[task.project_uuid],
            ),
        )
        for task, log_file in zip(comp_tasks, log_files, strict=True)
    ]

    return ComputationTaskRpcGetPage(
        items=comp_tasks_output,
        total=total,
    )


@router.expose(reraise_if_error_type=())
async def list_computation_collection_run_tasks_page(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    collection_run_id: CollectionRunID,
    # pagination
    offset: int = 0,
    limit: int = 20,
    # ordering
    order_by: OrderBy | None = None,
) -> ComputationCollectionRunTaskRpcGetPage:
    comp_runs_snapshot_tasks_repo = CompRunsSnapshotTasksRepository.instance(
        db_engine=app.state.engine
    )

    total, comp_tasks = (
        await comp_runs_snapshot_tasks_repo.list_computation_collection_run_tasks(
            product_name=product_name,
            user_id=user_id,
            collection_run_id=collection_run_id,
            offset=offset,
            limit=limit,
            order_by=order_by,
        )
    )

    # Run all log fetches concurrently
    log_files = await limited_gather(
        *[_fetch_task_log(user_id, task) for task in comp_tasks],
        limit=20,
    )

    comp_tasks_output = [
        ComputationCollectionRunTaskRpcGet(
            project_uuid=task.project_uuid,
            node_id=task.node_id,
            state=task.state,
            progress=task.progress,
            image=task.image,
            started_at=task.started_at,
            ended_at=task.ended_at,
            log_download_link=log_file.download_link if log_file else None,
            service_run_id=ServiceRunID.get_resource_tracking_run_id_for_computational(
                user_id,
                task.project_uuid,
                task.node_id,
                task.iteration,
            ),
        )
        for task, log_file in zip(comp_tasks, log_files, strict=True)
    ]

    return ComputationCollectionRunTaskRpcGetPage(
        items=comp_tasks_output,
        total=total,
    )
