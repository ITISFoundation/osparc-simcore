import logging
from typing import Dict, List

import networkx as nx
from celery.canvas import Signature
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from models_library.nodes import NodeID
from models_library.projects import ProjectID, RunningState, Workbench
from simcore_postgres_database.models.comp_tasks import NodeClass
from starlette import status
from starlette.requests import Request

from ...models.domains.comp_tasks import (
    CompTaskAtDB,
    ComputationTaskCreate,
    ComputationTaskOut,
    ComputationTaskStop,
)
from ...models.domains.projects import ProjectAtDB
from ...models.schemas.constants import UserID
from ...modules.db.repositories.computations import (
    CompPipelinesRepository,
    CompTasksRepository,
)
from ...modules.db.repositories.projects import ProjectsRepository
from ...modules.db.tables import NodeClass
from ...utils.computations import get_pipeline_state_from_task_states, to_node_class
from ...utils.exceptions import ProjectNotFoundError
from ..dependencies.celery import CeleryClient, get_celery_client
from ..dependencies.database import get_repository
from ..dependencies.director_v0 import DirectorV0Client, get_director_v0_client

router = APIRouter()
log = logging.getLogger(__file__)


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
        if to_node_class(node.key) == NodeClass.COMPUTATIONAL:
            dag_graph.add_node(
                node_id, name=node.label, key=node.key, version=node.version
            )
        for input_node_id in node.inputNodes:
            predecessor_node = workbench.get(input_node_id)
            if (
                predecessor_node
                and to_node_class(predecessor_node.key) == NodeClass.COMPUTATIONAL
            ):
                dag_graph.add_edge(input_node_id, node_id)
    log.debug("created DAG graph: %s", nx.to_dict_of_lists(dag_graph.adj))

    return dag_graph


def topological_sort_grouping(dag_graph: nx.DiGraph) -> List[Signature]:
    # copy the graph
    graph_copy = dag_graph.copy()
    res = []
    while graph_copy:
        zero_indegree = [v for v, d in graph_copy.in_degree() if d == 0]
        res.append(zero_indegree)
        graph_copy.remove_nodes_from(zero_indegree)
    return res


@router.post(
    "",
    summary="Create and Start a new computation",
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

        # check if current state allow to start the computation
        comp_tasks: Dict[NodeID, CompTaskAtDB] = await computation_tasks.get_comp_tasks(
            job.project_id
        )
        pipeline_state = get_pipeline_state_from_task_states(
            list(comp_tasks.values()), celery_client.settings.publication_timeout
        )
        if pipeline_state in [
            RunningState.PUBLISHED,
            RunningState.PENDING,
            RunningState.STARTED,
            RunningState.RETRY,
        ]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Projet {job.project_id} already started, current state is {pipeline_state}",
            )

        # create the DAG
        dag_graph = create_dag_graph(project.workbench)
        # validate DAG
        if not nx.is_directed_acyclic_graph(dag_graph):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project {job.project_id} is not a valid directed acyclic graph!",
            )
        # find the entrypoints
        entrypoints = find_entrypoints(dag_graph)
        if not entrypoints:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Project {job.project_id} has no services to compute",
            )
        # FIXME: directly pass the tasks to celery instead of the current recursive way
        await computation_pipelines.publish_pipeline(project.uuid, dag_graph)
        # ok so publish the tasks
        await computation_tasks.publish_tasks_from_project(project, director_client)
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
            state=task.state,
            url=f"{request.url}/{job.project_id}",
        )

    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get(
    "/{project_id}",
    response_model=ComputationTaskOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def get_computation(
    user_id: UserID,
    project_id: ProjectID,
    request: Request,
    project_repo: ProjectsRepository = Depends(get_repository(ProjectsRepository)),
    computation_tasks: CompTasksRepository = Depends(
        get_repository(CompTasksRepository)
    ),
    celery_client: CeleryClient = Depends(get_celery_client),
):
    log.debug("User %s getting computation status for project %s", user_id, project_id)
    try:
        # get the project
        project: ProjectAtDB = await project_repo.get_project(project_id)
        # get the project task states
        comp_tasks: Dict[NodeID, CompTaskAtDB] = await computation_tasks.get_comp_tasks(
            project_id
        )
        pipeline_state = get_pipeline_state_from_task_states(
            list(comp_tasks.values()), celery_client.settings.publication_timeout
        )

        log.debug(
            "Computational task status by user %s for project %s is %s",
            user_id,
            project_id,
            pipeline_state,
        )

        task_out = ComputationTaskOut(
            id=project.uuid,
            state=pipeline_state,
            url=f"{request.url.remove_query_params('user_id')}",
        )
        return task_out

    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

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
    summary="Stops a computation",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def stop_computation_project(
    comp_task_stop: ComputationTaskStop,
    project_id: ProjectID,
    project_repo: ProjectsRepository = Depends(get_repository(ProjectsRepository)),
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
        # check if current state allow to stop the computation
        comp_tasks: Dict[NodeID, CompTaskAtDB] = await computation_tasks.get_comp_tasks(
            project_id
        )
        pipeline_state = get_pipeline_state_from_task_states(
            list(comp_tasks.values()), celery_client.settings.publication_timeout
        )
        if pipeline_state not in [
            RunningState.PUBLISHED,
            RunningState.PENDING,
            RunningState.STARTED,
            RunningState.RETRY,
        ]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Projet {project_id} already completed, current state is {pipeline_state}",
            )

        await computation_tasks.abort_tasks_from_project(project)
        celery_client.abort_computation_tasks(
            [str(c.job_id) for c in comp_tasks.values()]
        )
        log.debug(
            "Computational task stopped by user %s for project %s",
            comp_task_stop.user_id,
            project_id,
        )

    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
