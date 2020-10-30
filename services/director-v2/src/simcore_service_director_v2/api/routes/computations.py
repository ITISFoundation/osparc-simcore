import logging
from typing import Dict, List

import networkx as nx
from celery.contrib.abortable import AbortableAsyncResult
from celery.result import AsyncResult
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from models_library.projects import (
    Node,
    NodeID,
    Project,
    ProjectID,
    RunningState,
    Workbench,
)
from simcore_service_director_v2.utils.exceptions import ProjectNotFoundError
from starlette import status
from starlette.requests import Request

from ...models.domains.comp_tasks import (
    CompTaskAtDB,
    ComputationTask,
    ComputationTaskOut,
    TaskID,
)
from ...models.domains.projects import ProjectAtDB
from ...models.schemas.constants import UserID
from ...modules.db.repositories.computations import (
    CompPipelinesRepository,
    CompTasksRepository,
)
from ...modules.db.repositories.projects import ProjectsRepository
from ...utils.computations import get_pipeline_state_from_task_states
from ..dependencies.celery import CeleryClient, get_celery_client
from ..dependencies.database import get_repository
from ..dependencies.director_v0 import DirectorV0Client, get_director_v0_client

router = APIRouter()
log = logging.getLogger(__file__)


@router.get("")
async def list_computations(
    user_id: UserID,
    computation_pipelines: CompPipelinesRepository = Depends(
        get_repository(CompPipelinesRepository)
    ),
    computation_tasks: CompTasksRepository = Depends(
        get_repository(CompTasksRepository)
    ),
):
    pass


def celery_on_message(body):
    log.warning(body)


def background_on_message(task):
    log.warning(task.get(on_message=celery_on_message, propagate=False))


def find_entrypoints(graph: nx.DiGraph) -> List[NodeID]:
    entrypoints = [n for n in graph.nodes if not list(graph.predecessors(n))]
    log.debug("the entrypoints of the graph are %s", entrypoints)
    return entrypoints


def create_dag_graph(workbench: Workbench) -> nx.DiGraph:
    dag_graph = nx.DiGraph()
    for node_id, node in workbench.items():
        dag_graph.add_node(node_id)
        for input_node_id in node.inputNodes:
            dag_graph.add_edge(input_node_id, node_id)
    log.debug("created DAG graph: %s", dag_graph.adj)

    return dag_graph


@router.post(
    "",
    description="Create and Start a new computation",
    response_model=ComputationTaskOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_computation(
    user_id: UserID,
    project_id: ProjectID,
    background_tasks: BackgroundTasks,
    request: Request,
    project_repo: ProjectsRepository = Depends(get_repository(ProjectsRepository)),
    computation_tasks: CompTasksRepository = Depends(
        get_repository(CompTasksRepository)
    ),
    celery_client: CeleryClient = Depends(get_celery_client),
    director_client: DirectorV0Client = Depends(get_director_v0_client),
):
    try:
        # get the project
        project: ProjectAtDB = await project_repo.get_project(project_id)

        # check if current state allow to start the computation
        comp_tasks: Dict[NodeID, CompTaskAtDB] = await computation_tasks.get_comp_tasks(
            project_id
        )
        pipeline_state = get_pipeline_state_from_task_states(comp_tasks)
        if pipeline_state in [
            RunningState.PUBLISHED,
            RunningState.PENDING,
            RunningState.STARTED,
            RunningState.RETRY,
        ]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Projet {project_id} already started, current state is {pipeline_state}",
            )

        # create the DAG
        dag_graph = create_dag_graph(project.workbench)
        # find the entrypoints
        entrypoints = find_entrypoints(dag_graph)
        # ok so publish the tasks
        await computation_tasks.publish_tasks(project_id)
        # trigger celery
        task = celery_client.send_computation_task(user_id, project_id)
        background_tasks.add_task(background_on_message, task)
        return ComputationTaskOut(
            id=task.id, state=task.state, url=f"{request.base_url}{task.id}"
        )

    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get(
    "/{computation_id}",
    response_model=ComputationTask,
    status_code=status.HTTP_202_ACCEPTED,
)
async def get_computation(computation_id: TaskID):
    task = AsyncResult(str(computation_id))
    if task.state == RunningState.SUCCESS:
        return ComputationTask(id=task.id, state=task.state, result=task.result)
    if task.state == RunningState.FAILED:
        return ComputationTask(
            id=task.id,
            state=task.state,
            result=task.backend.get(task.backend.get_key_for_task(task.id)),
        )
    return ComputationTask(id=task.id, state=task.state, result=task.info)


@router.delete(
    "/{computation_id}",
    description="Stops a computation",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def stop_computation(computation_id: TaskID):
    abortable_task = AbortableAsyncResult(str(computation_id))
    abortable_task.abort()
