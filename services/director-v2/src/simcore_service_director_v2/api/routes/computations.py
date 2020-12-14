import logging
from typing import List

import networkx as nx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from simcore_service_director_v2.models.domains.comp_pipelines import CompPipelineAtDB
from starlette import status
from starlette.requests import Request
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_result,
    stop_after_delay,
    wait_random,
)

from ...models.domains.comp_tasks import (
    CompTaskAtDB,
    ComputationTaskCreate,
    ComputationTaskDelete,
    ComputationTaskOut,
    ComputationTaskStop,
)
from ...models.domains.projects import ProjectAtDB
from ...models.schemas.constants import UserID
from ...modules.db.repositories.comp_pipelines import CompPipelinesRepository
from ...modules.db.repositories.comp_tasks import CompTasksRepository
from ...modules.db.repositories.projects import ProjectsRepository
from ...utils.computations import (
    get_pipeline_state_from_task_states,
    is_pipeline_running,
    is_pipeline_stopped,
)
from ...utils.dags import create_dag_graph, create_minimal_graph_based_on_selection
from ...utils.exceptions import ProjectNotFoundError
from ..dependencies.celery import CeleryClient, get_celery_client
from ..dependencies.database import get_repository
from ..dependencies.director_v0 import DirectorV0Client, get_director_v0_client

router = APIRouter()
log = logging.getLogger(__file__)

PIPELINE_ABORT_TIMEOUT_S = 10


def celery_on_message(body):
    # FIXME: this might become handy when we stop starting tasks recursively
    log.warning(body)


def background_on_message(task):
    # FIXME: this might become handy when we stop starting tasks recursively
    log.warning(task.get(on_message=celery_on_message, propagate=False))


async def _abort_pipeline_tasks(
    project: ProjectAtDB,
    tasks: List[CompTaskAtDB],
    computation_tasks: CompTasksRepository,
    celery_client: CeleryClient,
):
    await computation_tasks.mark_project_tasks_as_aborted(project)
    celery_client.abort_computation_tasks([str(t.job_id) for t in tasks])
    log.debug(
        "Computational task stopped for project %s",
        project.uuid,
    )


@router.post(
    "",
    summary="Create and optionally start a new computation",
    response_model=ComputationTaskOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_computation(
    # pylint: disable=too-many-arguments
    job: ComputationTaskCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    project_repo: ProjectsRepository = Depends(get_repository(ProjectsRepository)),
    computation_pipelines: CompPipelinesRepository = Depends(
        get_repository(CompPipelinesRepository)
    ),
    computation_tasks: CompTasksRepository = Depends(
        get_repository(CompTasksRepository)
    ),
    celery_client: CeleryClient = Depends(get_celery_client),
    director_client: DirectorV0Client = Depends(get_director_v0_client),
):
    log.debug(
        "User %s is creating a new computation from project %s",
        job.user_id,
        job.project_id,
    )
    try:
        # get the project
        project: ProjectAtDB = await project_repo.get_project(job.project_id)

        # FIXME: this could not be valid anymore if the user deletes the project in between right?
        # check if current state allow to modify the computation
        comp_tasks: List[CompTaskAtDB] = await computation_tasks.get_comp_tasks(
            job.project_id
        )
        pipeline_state = get_pipeline_state_from_task_states(
            comp_tasks, celery_client.settings.publication_timeout
        )
        if is_pipeline_running(pipeline_state):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Projet {job.project_id} already started, current state is {pipeline_state}",
            )

        # create the computational DAG
        dag_graph = create_dag_graph(project.workbench)
        # validate DAG
        if not nx.is_directed_acyclic_graph(dag_graph):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project {job.project_id} is not a valid directed acyclic graph!",
            )
        # get a subgraph if needed
        if job.subgraph:
            dag_graph = create_minimal_graph_based_on_selection(dag_graph, job.subgraph)

        # ok so put the tasks in the db
        await computation_pipelines.upsert_pipeline(
            project.uuid, dag_graph, job.start_pipeline
        )
        await computation_tasks.upsert_tasks_from_project(
            project,
            director_client,
            list(dag_graph.nodes()) if job.start_pipeline else [],
        )

        if job.start_pipeline:
            # trigger celery
            task = celery_client.send_computation_task(job.user_id, job.project_id)
            background_tasks.add_task(background_on_message, task)
            log.debug(
                "Started computational task %s for user %s based on project %s",
                task.id,
                job.user_id,
                job.project_id,
            )

        return ComputationTaskOut(
            id=job.project_id,
            state=RunningState.PUBLISHED
            if job.start_pipeline
            else RunningState.NOT_STARTED,
            pipeline=nx.to_dict_of_lists(dag_graph),
            url=f"{request.url}/{job.project_id}",
            stop_url=f"{request.url}/{job.project_id}:stop"
            if job.start_pipeline
            else None,
        )

    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get(
    "/{project_id}",
    summary="Returns a computation pipeline state",
    response_model=ComputationTaskOut,
    status_code=status.HTTP_202_ACCEPTED,
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
    celery_client: CeleryClient = Depends(get_celery_client),
):
    log.debug("User %s getting computation status for project %s", user_id, project_id)
    try:
        # check that project actually exists
        # TODO: get a copy of the project and process it here instead!
        await project_repo.get_project(project_id)

        # get the project pipeline
        pipeline_at_db: CompPipelineAtDB = await computation_pipelines.get_pipeline(
            project_id
        )

        # get the project task states
        comp_tasks: List[CompTaskAtDB] = await computation_tasks.get_comp_tasks(
            project_id
        )
        dag_graph: nx.DiGraph = nx.from_dict_of_lists(pipeline_at_db.dag_adjacency_list)
        # filter the tasks by the effective pipeline
        filtered_tasks = [
            t for t in comp_tasks if str(t.node_id) in list(dag_graph.nodes())
        ]
        pipeline_state = get_pipeline_state_from_task_states(
            filtered_tasks, celery_client.settings.publication_timeout
        )

        log.debug(
            "Computational task status by user %s for project %s is %s",
            user_id,
            project_id,
            pipeline_state,
        )

        task_out = ComputationTaskOut(
            id=project_id,
            state=pipeline_state,
            pipeline=pipeline_at_db.dag_adjacency_list,
            url=f"{request.url.remove_query_params('user_id')}",
            stop_url=f"{request.url.remove_query_params('user_id')}:stop"
            if is_pipeline_running(pipeline_state)
            else None,
        )
        return task_out

    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    # NOTE: this will be re-used for the prep2go API stuff... don't worry...
    # task = AsyncResult(str(computation_id))
    # if task.state == RunningState.SUCCESS:
    #     return ComputationTask(id=task.id, state=task.state, result=task.result)
    # if task.state == RunningState.FAILED:
    #     return ComputationTask(
    #         id=task.id,
    #         state=task.state,
    #         result=task.backend.get(task.backend.get_key_for_task(task.id)),
    #     )
    # return ComputationTask(id=task.id, state=task.state, result=task.info)


@router.post(
    "/{project_id}:stop",
    summary="Stops a computation pipeline",
    response_model=None,
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
    celery_client: CeleryClient = Depends(get_celery_client),
):
    log.debug(
        "User %s stopping computation for project %s",
        comp_task_stop.user_id,
        project_id,
    )
    try:
        # get the project
        project: ProjectAtDB = await project_repo.get_project(project_id)
        # get the project pipeline
        pipeline_at_db: CompPipelineAtDB = await computation_pipelines.get_pipeline(
            project_id
        )
        # check if current state allow to stop the computation
        comp_tasks: List[CompTaskAtDB] = await computation_tasks.get_comp_tasks(
            project_id
        )
        pipeline_state = get_pipeline_state_from_task_states(
            comp_tasks, celery_client.settings.publication_timeout
        )

        if is_pipeline_running(pipeline_state):
            await _abort_pipeline_tasks(
                project, comp_tasks, computation_tasks, celery_client
            )
        return ComputationTaskOut(
            id=project_id,
            state=pipeline_state,
            pipeline=pipeline_at_db.dag_adjacency_list,
            url=f"{str(request.url).rstrip(':stop')}",
        )

    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


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
    celery_client: CeleryClient = Depends(get_celery_client),
):
    try:
        # get the project
        project: ProjectAtDB = await project_repo.get_project(project_id)
        # check if current state allow to stop the computation
        comp_tasks: List[CompTaskAtDB] = await computation_tasks.get_comp_tasks(
            project_id
        )
        pipeline_state = get_pipeline_state_from_task_states(
            comp_tasks, celery_client.settings.publication_timeout
        )
        if is_pipeline_running(pipeline_state):
            if not comp_task_stop.force:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Projet {project_id} is currently running and cannot be deleted, current state is {pipeline_state}",
                )
            # abort the pipeline first
            await _abort_pipeline_tasks(
                project, comp_tasks, computation_tasks, celery_client
            )

            def return_last_value(retry_state):
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
                    celery_client.settings.publication_timeout,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
