# pylint: disable=too-many-arguments

import contextlib
import logging
from typing import Any, List, Optional

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException
from models_library.clusters import DEFAULT_CLUSTER_ID
from models_library.projects import ProjectAtDB, ProjectID
from models_library.users import UserID
from pydantic import AnyHttpUrl, parse_obj_as
from servicelib.async_utils import run_sequentially_in_context
from simcore_service_director_v2.models.domains.comp_runs import CompRunsAtDB
from starlette import status
from starlette.requests import Request
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_result
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random

from ...core.errors import (
    ComputationalRunNotFoundError,
    ProjectNotFoundError,
    SchedulerError,
)
from ...models.domains.comp_pipelines import CompPipelineAtDB
from ...models.domains.comp_tasks import CompTaskAtDB
from ...models.schemas.comp_tasks import (
    ComputationTaskCreate,
    ComputationTaskDelete,
    ComputationTaskGet,
    ComputationTaskStop,
)
from ...modules.comp_scheduler.base_scheduler import BaseCompScheduler
from ...modules.db.repositories.comp_pipelines import CompPipelinesRepository
from ...modules.db.repositories.comp_runs import CompRunsRepository
from ...modules.db.repositories.comp_tasks import CompTasksRepository
from ...modules.db.repositories.projects import ProjectsRepository
from ...modules.director_v0 import DirectorV0Client
from ...utils.computations import (
    get_pipeline_state_from_task_states,
    is_pipeline_running,
    is_pipeline_stopped,
)
from ...utils.dags import (
    compute_pipeline_details,
    create_complete_dag,
    create_complete_dag_from_tasks,
    create_minimal_computational_graph_based_on_selection,
    find_computational_node_cycles,
)
from ..dependencies.database import get_repository
from ..dependencies.director_v0 import get_director_v0_client
from ..dependencies.scheduler import get_scheduler

router = APIRouter()
log = logging.getLogger(__name__)

PIPELINE_ABORT_TIMEOUT_S = 10


@router.post(
    "",
    summary="Create and optionally start a new computation",
    response_model=ComputationTaskGet,
    status_code=status.HTTP_201_CREATED,
)
# NOTE: in case of a burst of calls to that endpoint, we might end up in a weird state.
@run_sequentially_in_context(target_args=["job.project_id"])
async def create_computation(
    job: ComputationTaskCreate,
    request: Request,
    project_repo: ProjectsRepository = Depends(get_repository(ProjectsRepository)),
    computation_pipelines: CompPipelinesRepository = Depends(
        get_repository(CompPipelinesRepository)
    ),
    computation_tasks: CompTasksRepository = Depends(
        get_repository(CompTasksRepository)
    ),
    director_client: DirectorV0Client = Depends(get_director_v0_client),
    scheduler: BaseCompScheduler = Depends(get_scheduler),
) -> ComputationTaskGet:
    log.debug(
        "User %s is creating a new computation from project %s",
        f"{job.user_id=}",
        f"{job.project_id=}",
    )
    try:
        # get the project
        project: ProjectAtDB = await project_repo.get_project(job.project_id)

        # FIXME: this could not be valid anymore if the user deletes the project in between right?

        # check if current state allow to modify the computation
        comp_tasks: List[CompTaskAtDB] = await computation_tasks.get_comp_tasks(
            job.project_id
        )
        pipeline_state = get_pipeline_state_from_task_states(comp_tasks)
        if is_pipeline_running(pipeline_state):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Project {job.project_id} already started, current state is {pipeline_state}",
            )

        # create the complete DAG graph
        complete_dag = create_complete_dag(project.workbench)
        # find the minimal viable graph to be run
        minimal_computational_dag: nx.DiGraph = (
            await create_minimal_computational_graph_based_on_selection(
                complete_dag=complete_dag,
                selected_nodes=job.subgraph or [],
                force_restart=job.force_restart or False,
            )
        )

        # ok so put the tasks in the db
        await computation_pipelines.upsert_pipeline(
            project.uuid,
            minimal_computational_dag,
            publish=job.start_pipeline or False,
        )
        inserted_comp_tasks = await computation_tasks.upsert_tasks_from_project(
            project,
            director_client,
            published_nodes=list(minimal_computational_dag.nodes())
            if job.start_pipeline
            else [],
        )

        if job.start_pipeline:
            if not minimal_computational_dag.nodes():
                # 2 options here: either we have cycles in the graph or it's really done
                list_of_cycles = find_computational_node_cycles(complete_dag)
                if list_of_cycles:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Project {job.project_id} contains cycles with computational services which are currently not supported! Please remove them.",
                    )
                # there is nothing else to be run here, so we are done
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Project {job.project_id} has no computational services",
                )

            await scheduler.run_new_pipeline(
                job.user_id,
                job.project_id,
                job.cluster_id or DEFAULT_CLUSTER_ID,
            )

        # filter the tasks by the effective pipeline
        filtered_tasks = [
            t
            for t in inserted_comp_tasks
            if f"{t.node_id}" in set(minimal_computational_dag.nodes())
        ]
        pipeline_state = get_pipeline_state_from_task_states(filtered_tasks)

        return ComputationTaskGet(
            id=job.project_id,
            state=pipeline_state,
            pipeline_details=await compute_pipeline_details(
                complete_dag, minimal_computational_dag, inserted_comp_tasks
            ),
            url=f"{request.url}/{job.project_id}",
            stop_url=f"{request.url}/{job.project_id}:stop"
            if job.start_pipeline
            else None,
        )

    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{e}") from e


@router.get(
    "/{project_id}",
    summary="Returns a computation pipeline state",
    response_model=ComputationTaskGet,
    status_code=status.HTTP_200_OK,
)
async def get_computation(
    user_id: UserID,
    project_id: ProjectID,
    request: Request,
    project_repo: ProjectsRepository = Depends(get_repository(ProjectsRepository)),
    computation_pipelines: CompPipelinesRepository = Depends(
        get_repository(CompPipelinesRepository)
    ),
    computation_tasks: CompTasksRepository = Depends(
        get_repository(CompTasksRepository)
    ),
    computation_runs: CompRunsRepository = Depends(get_repository(CompRunsRepository)),
) -> ComputationTaskGet:
    log.debug(
        "User %s getting computation status for project %s",
        f"{user_id=}",
        f"{project_id=}",
    )

    # check that project actually exists
    await project_repo.get_project(project_id)

    # NOTE: Here it is assumed the project exists in comp_tasks/comp_pipeline
    # get the project pipeline
    pipeline_at_db: CompPipelineAtDB = await computation_pipelines.get_pipeline(
        project_id
    )
    pipeline_dag: nx.DiGraph = pipeline_at_db.get_graph()

    # get the project task states
    all_tasks: List[CompTaskAtDB] = await computation_tasks.get_all_tasks(project_id)

    # filter the tasks by the effective pipeline
    filtered_tasks = [
        t for t in all_tasks if f"{t.node_id}" in set(pipeline_dag.nodes())
    ]

    # check that we have the expected tasks
    if len(filtered_tasks) != len(pipeline_dag):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The tasks referenced by the pipeline are missing",
        )

    pipeline_state = get_pipeline_state_from_task_states(filtered_tasks)

    log.debug(
        "Computational task status by %s for %s has %s",
        f"{user_id=}",
        f"{project_id=}",
        f"{pipeline_state=}",
    )

    # create the complete DAG graph
    complete_dag = create_complete_dag_from_tasks(all_tasks)
    pipeline_details = await compute_pipeline_details(
        complete_dag, pipeline_dag, all_tasks
    )

    # get run details if any
    last_run: Optional[CompRunsAtDB] = None
    with contextlib.suppress(ComputationalRunNotFoundError):
        last_run = await computation_runs.get(user_id=user_id, project_id=project_id)

    self_url = request.url.remove_query_params("user_id")
    task_out = ComputationTaskGet(
        id=project_id,
        state=pipeline_state,
        pipeline_details=pipeline_details,
        url=parse_obj_as(AnyHttpUrl, f"{request.url}"),
        stop_url=parse_obj_as(AnyHttpUrl, f"{self_url}:stop?user_id={user_id}")
        if pipeline_state.is_running()
        else None,
        iteration=last_run.iteration if last_run else None,
        cluster_id=last_run.cluster_id if last_run else None,
        result=None,
    )
    return task_out


@router.post(
    "/{project_id}:stop",
    summary="Stops a computation pipeline",
    response_model=ComputationTaskGet,
    status_code=status.HTTP_202_ACCEPTED,
)
async def stop_computation_project(
    comp_task_stop: ComputationTaskStop,
    project_id: ProjectID,
    request: Request,
    project_repo: ProjectsRepository = Depends(get_repository(ProjectsRepository)),
    computation_pipelines: CompPipelinesRepository = Depends(
        get_repository(CompPipelinesRepository)
    ),
    computation_tasks: CompTasksRepository = Depends(
        get_repository(CompTasksRepository)
    ),
    scheduler: BaseCompScheduler = Depends(get_scheduler),
) -> ComputationTaskGet:
    log.debug(
        "User %s stopping computation for project %s",
        comp_task_stop.user_id,
        project_id,
    )
    try:
        # check the project exists
        await project_repo.get_project(project_id)
        # get the project pipeline
        pipeline_at_db: CompPipelineAtDB = await computation_pipelines.get_pipeline(
            project_id
        )
        pipeline_dag: nx.DiGraph = pipeline_at_db.get_graph()
        # get the project task states
        tasks: List[CompTaskAtDB] = await computation_tasks.get_all_tasks(project_id)
        # create the complete DAG graph
        complete_dag = create_complete_dag_from_tasks(tasks)
        # filter the tasks by the effective pipeline
        filtered_tasks = [
            t for t in tasks if f"{t.node_id}" in set(pipeline_dag.nodes())
        ]
        pipeline_state = get_pipeline_state_from_task_states(filtered_tasks)

        if is_pipeline_running(pipeline_state):
            await scheduler.stop_pipeline(comp_task_stop.user_id, project_id)

        return ComputationTaskGet(
            id=project_id,
            state=pipeline_state,
            pipeline_details=await compute_pipeline_details(
                complete_dag, pipeline_dag, tasks
            ),
            url=f"{str(request.url).rstrip(':stop')}",
        )

    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{e}") from e
    except SchedulerError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{e}") from e


@router.delete(
    "/{project_id}",
    summary="Deletes a computation pipeline",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_pipeline(
    comp_task_stop: ComputationTaskDelete,
    project_id: ProjectID,
    project_repo: ProjectsRepository = Depends(get_repository(ProjectsRepository)),
    computation_pipelines: CompPipelinesRepository = Depends(
        get_repository(CompPipelinesRepository)
    ),
    computation_tasks: CompTasksRepository = Depends(
        get_repository(CompTasksRepository)
    ),
    scheduler: BaseCompScheduler = Depends(get_scheduler),
) -> None:
    try:
        # get the project
        project: ProjectAtDB = await project_repo.get_project(project_id)
        # check if current state allow to stop the computation
        comp_tasks: List[CompTaskAtDB] = await computation_tasks.get_comp_tasks(
            project_id
        )
        pipeline_state = get_pipeline_state_from_task_states(comp_tasks)
        if is_pipeline_running(pipeline_state):
            if not comp_task_stop.force:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Projet {project_id} is currently running and cannot be deleted, current state is {pipeline_state}",
                )
            # abort the pipeline first
            try:
                await scheduler.stop_pipeline(comp_task_stop.user_id, project_id)
            except SchedulerError as e:
                log.warning(
                    "Project %s could not be stopped properly.\n reason: %s",
                    project_id,
                    e,
                )

            def return_last_value(retry_state: Any) -> Any:
                """return the result of the last call attempt"""
                return retry_state.outcome.result()

            @retry(
                stop=stop_after_delay(PIPELINE_ABORT_TIMEOUT_S),
                wait=wait_random(0, 2),
                retry_error_callback=return_last_value,
                retry=retry_if_result(lambda result: result is False),
                reraise=False,
                before_sleep=before_sleep_log(log, logging.INFO),
            )
            async def check_pipeline_stopped() -> bool:
                comp_tasks: List[CompTaskAtDB] = await computation_tasks.get_comp_tasks(
                    project_id
                )
                pipeline_state = get_pipeline_state_from_task_states(
                    comp_tasks,
                )
                return is_pipeline_stopped(pipeline_state)

            # wait for the pipeline to be stopped
            if not await check_pipeline_stopped():
                log.error(
                    "pipeline %s could not be stopped properly after %ss",
                    project_id,
                    PIPELINE_ABORT_TIMEOUT_S,
                )

        # delete the pipeline now
        await computation_tasks.delete_tasks_from_project(project)
        await computation_pipelines.delete_pipeline(project_id)

    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{e}") from e
