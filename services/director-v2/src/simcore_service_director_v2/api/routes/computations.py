""" CRUD operations on a "computation" resource

A computation is a resource that represents a running pipeline of computational services in a give project
Therefore,
 - creating a computation will run the project's pipeline
 - the computation ID is the same as the associated project uuid


A task is computation sub-resource that respresents a running computational service in the pipeline described above
Therefore,
 - the task ID is the same as the associated node uuid

"""

# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


import contextlib
import logging
from typing import Annotated, Any, Final

import networkx as nx
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from models_library.api_schemas_directorv2.comp_tasks import (
    ComputationCreate,
    ComputationDelete,
    ComputationGet,
    ComputationStop,
)
from models_library.clusters import DEFAULT_CLUSTER_ID
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes_io import NodeID, NodeIDStr
from models_library.projects_state import RunningState
from models_library.services import ServiceKeyVersion
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyHttpUrl, TypeAdapter
from servicelib.async_utils import run_sequentially_in_context
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient
from simcore_postgres_database.utils_projects_metadata import DBProjectNotFoundError
from starlette import status
from starlette.requests import Request
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_result
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random

from ...core.errors import (
    ClusterAccessForbiddenError,
    ClusterNotFoundError,
    ClustersKeeperNotAvailableError,
    ComputationalRunNotFoundError,
    ComputationalSchedulerError,
    ConfigurationError,
    PricingPlanUnitNotFoundError,
    ProjectNotFoundError,
    WalletNotEnoughCreditsError,
)
from ...models.comp_pipelines import CompPipelineAtDB
from ...models.comp_runs import CompRunsAtDB, ProjectMetadataDict, RunMetadataDict
from ...models.comp_tasks import CompTaskAtDB
from ...modules.catalog import CatalogClient
from ...modules.comp_scheduler import run_new_pipeline, stop_pipeline
from ...modules.db.repositories.clusters import ClustersRepository
from ...modules.db.repositories.comp_pipelines import CompPipelinesRepository
from ...modules.db.repositories.comp_runs import CompRunsRepository
from ...modules.db.repositories.comp_tasks import CompTasksRepository
from ...modules.db.repositories.projects import ProjectsRepository
from ...modules.db.repositories.projects_metadata import ProjectsMetadataRepository
from ...modules.db.repositories.users import UsersRepository
from ...modules.director_v0 import DirectorV0Client
from ...modules.resource_usage_tracker_client import ResourceUsageTrackerClient
from ...utils import computations as utils
from ...utils.dags import (
    compute_pipeline_details,
    compute_pipeline_started_timestamp,
    compute_pipeline_stopped_timestamp,
    compute_pipeline_submitted_timestamp,
    create_complete_dag,
    create_complete_dag_from_tasks,
    create_minimal_computational_graph_based_on_selection,
    find_computational_node_cycles,
)
from ..dependencies.catalog import get_catalog_client
from ..dependencies.database import get_repository
from ..dependencies.director_v0 import get_director_v0_client
from ..dependencies.rabbitmq import rabbitmq_rpc_client
from ..dependencies.rut_client import get_rut_client
from .computations_tasks import analyze_pipeline

_PIPELINE_ABORT_TIMEOUT_S: Final[int] = 10

_logger = logging.getLogger(__name__)

router = APIRouter()


async def _check_pipeline_not_running_or_raise_409(
    comp_tasks_repo: CompTasksRepository, computation: ComputationCreate
) -> None:
    pipeline_state = utils.get_pipeline_state_from_task_states(
        await comp_tasks_repo.list_computational_tasks(computation.project_id)
    )
    if utils.is_pipeline_running(pipeline_state):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project {computation.project_id} already started, current state is {pipeline_state}",
        )


async def _check_pipeline_startable(
    pipeline_dag: nx.DiGraph,
    computation: ComputationCreate,
    catalog_client: CatalogClient,
    clusters_repo: ClustersRepository,
) -> None:
    assert computation.product_name  # nosec
    if deprecated_tasks := await utils.find_deprecated_tasks(
        computation.user_id,
        computation.product_name,
        [
            ServiceKeyVersion(key=node[1]["key"], version=node[1]["version"])
            for node in pipeline_dag.nodes.data()
        ],
        catalog_client,
    ):
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"Project {computation.project_id} cannot run since it contains deprecated tasks {jsonable_encoder( deprecated_tasks)}",
        )
    if computation.cluster_id:
        # check the cluster ID is a valid one
        try:
            await clusters_repo.get_cluster(computation.user_id, computation.cluster_id)
        except ClusterNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
                detail=f"Project {computation.project_id} cannot run on cluster {computation.cluster_id}, not found",
            ) from exc
        except ClusterAccessForbiddenError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Project {computation.project_id} cannot run on cluster {computation.cluster_id}, no access",
            ) from exc


_UNKNOWN_NODE: Final[str] = "unknown node"


@log_decorator(_logger)
async def _get_project_metadata(
    project_id: ProjectID,
    project_repo: ProjectsRepository,
    projects_metadata_repo: ProjectsMetadataRepository,
) -> ProjectMetadataDict:
    try:
        project_ancestors = await projects_metadata_repo.get_project_ancestors(
            project_id
        )
        if project_ancestors.parent_project_uuid is None:
            _logger.debug("no parent found for project %s", project_id)
            return {}

        assert project_ancestors.parent_node_id is not None  # nosec
        assert project_ancestors.root_project_uuid is not None  # nosec
        assert project_ancestors.root_node_id is not None  # nosec

        async def _get_project_node_names(
            project_uuid: ProjectID, node_id: NodeID
        ) -> tuple[str, str]:
            prj = await project_repo.get_project(project_uuid)
            node_id_str = NodeIDStr(f"{node_id}")
            if node_id_str not in prj.workbench:
                _logger.error(
                    "%s not found in %s. it is an ancestor of %s. Please check!",
                    f"{node_id=}",
                    f"{prj.uuid=}",
                    f"{project_id=}",
                )
                return prj.name, _UNKNOWN_NODE
            return prj.name, prj.workbench[node_id_str].label

        parent_project_name, parent_node_name = await _get_project_node_names(
            project_ancestors.parent_project_uuid, project_ancestors.parent_node_id
        )
        root_parent_project_name, root_parent_node_name = await _get_project_node_names(
            project_ancestors.root_project_uuid, project_ancestors.root_node_id
        )
        return ProjectMetadataDict(
            parent_node_id=project_ancestors.parent_node_id,
            parent_node_name=parent_node_name,
            parent_project_id=project_ancestors.parent_project_uuid,
            parent_project_name=parent_project_name,
            root_parent_node_id=project_ancestors.root_node_id,
            root_parent_node_name=root_parent_node_name,
            root_parent_project_id=project_ancestors.root_project_uuid,
            root_parent_project_name=root_parent_project_name,
        )

    except DBProjectNotFoundError:
        _logger.exception("Could not find project: %s", f"{project_id=}")
    except ProjectNotFoundError as exc:
        _logger.exception(
            "Could not find parent project: %s", exc.error_context().get("project_id")
        )

    return {}


async def _try_start_pipeline(
    app: FastAPI,
    *,
    project_repo: ProjectsRepository,
    computation: ComputationCreate,
    complete_dag: nx.DiGraph,
    minimal_dag: nx.DiGraph,
    project: ProjectAtDB,
    users_repo: UsersRepository,
    projects_metadata_repo: ProjectsMetadataRepository,
) -> None:
    if not minimal_dag.nodes():
        # 2 options here: either we have cycles in the graph or it's really done
        if find_computational_node_cycles(complete_dag):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project {computation.project_id} contains cycles with computational services which are currently not supported! Please remove them.",
            )
        # there is nothing else to be run here, so we are done
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Project {computation.project_id} has no computational services",
        )

    # Billing info
    wallet_id = None
    wallet_name = None
    if computation.wallet_info:
        wallet_id = computation.wallet_info.wallet_id
        wallet_name = computation.wallet_info.wallet_name

    await run_new_pipeline(
        app,
        user_id=computation.user_id,
        project_id=computation.project_id,
        cluster_id=computation.cluster_id or DEFAULT_CLUSTER_ID,
        run_metadata=RunMetadataDict(
            node_id_names_map={
                NodeID(node_idstr): node_data.label
                for node_idstr, node_data in project.workbench.items()
            },
            product_name=computation.product_name,
            project_name=project.name,
            simcore_user_agent=computation.simcore_user_agent,
            user_email=await users_repo.get_user_email(computation.user_id),
            wallet_id=wallet_id,
            wallet_name=wallet_name,
            project_metadata=await _get_project_metadata(
                computation.project_id, project_repo, projects_metadata_repo
            ),
        )
        or {},
        use_on_demand_clusters=computation.use_on_demand_clusters,
    )


@router.post(
    "",
    summary="Create and optionally start a new computation",
    response_model=ComputationGet,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Project or pricing details not found",
        },
        status.HTTP_406_NOT_ACCEPTABLE: {
            "description": "Cluster not found",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Service not available",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Configuration error",
        },
        status.HTTP_402_PAYMENT_REQUIRED: {"description": "Payment required"},
        status.HTTP_409_CONFLICT: {"description": "Project already started"},
    },
)
# NOTE: in case of a burst of calls to that endpoint, we might end up in a weird state.
@run_sequentially_in_context(target_args=["computation.project_id"])
async def create_computation(  # noqa: PLR0913 # pylint: disable=too-many-positional-arguments
    computation: ComputationCreate,
    request: Request,
    project_repo: Annotated[
        ProjectsRepository, Depends(get_repository(ProjectsRepository))
    ],
    comp_pipelines_repo: Annotated[
        CompPipelinesRepository, Depends(get_repository(CompPipelinesRepository))
    ],
    comp_tasks_repo: Annotated[
        CompTasksRepository, Depends(get_repository(CompTasksRepository))
    ],
    comp_runs_repo: Annotated[
        CompRunsRepository, Depends(get_repository(CompRunsRepository))
    ],
    clusters_repo: Annotated[
        ClustersRepository, Depends(get_repository(ClustersRepository))
    ],
    users_repo: Annotated[UsersRepository, Depends(get_repository(UsersRepository))],
    projects_metadata_repo: Annotated[
        ProjectsMetadataRepository, Depends(get_repository(ProjectsMetadataRepository))
    ],
    director_client: Annotated[DirectorV0Client, Depends(get_director_v0_client)],
    catalog_client: Annotated[CatalogClient, Depends(get_catalog_client)],
    rut_client: Annotated[ResourceUsageTrackerClient, Depends(get_rut_client)],
    rpc_client: Annotated[RabbitMQRPCClient, Depends(rabbitmq_rpc_client)],
) -> ComputationGet:
    _logger.debug(
        "User %s is creating a new computation from project %s",
        f"{computation.user_id=}",
        f"{computation.project_id=}",
    )
    try:
        # get the project
        project: ProjectAtDB = await project_repo.get_project(computation.project_id)

        # check if current state allow to modify the computation
        await _check_pipeline_not_running_or_raise_409(comp_tasks_repo, computation)

        # create the complete DAG graph
        complete_dag = create_complete_dag(project.workbench)
        # find the minimal viable graph to be run
        minimal_computational_dag: nx.DiGraph = (
            await create_minimal_computational_graph_based_on_selection(
                complete_dag=complete_dag,
                selected_nodes=computation.subgraph or [],
                force_restart=computation.force_restart or False,
            )
        )

        if computation.start_pipeline:
            await _check_pipeline_startable(
                minimal_computational_dag, computation, catalog_client, clusters_repo
            )

        # ok so put the tasks in the db
        await comp_pipelines_repo.upsert_pipeline(
            project.uuid,
            minimal_computational_dag,
            publish=computation.start_pipeline or False,
        )
        assert computation.product_name  # nosec
        min_computation_nodes: list[NodeID] = [
            NodeID(n) for n in minimal_computational_dag.nodes()
        ]
        comp_tasks = await comp_tasks_repo.upsert_tasks_from_project(
            project=project,
            catalog_client=catalog_client,
            director_client=director_client,
            published_nodes=min_computation_nodes if computation.start_pipeline else [],
            user_id=computation.user_id,
            product_name=computation.product_name,
            rut_client=rut_client,
            wallet_info=computation.wallet_info,
            rabbitmq_rpc_client=rpc_client,
        )

        if computation.start_pipeline:
            await _try_start_pipeline(
                request.app,
                project_repo=project_repo,
                computation=computation,
                complete_dag=complete_dag,
                minimal_dag=minimal_computational_dag,
                project=project,
                users_repo=users_repo,
                projects_metadata_repo=projects_metadata_repo,
            )

        # filter the tasks by the effective pipeline
        filtered_tasks = [
            t
            for t in comp_tasks
            if f"{t.node_id}" in set(minimal_computational_dag.nodes())
        ]
        pipeline_state = utils.get_pipeline_state_from_task_states(filtered_tasks)

        # get run details if any
        last_run: CompRunsAtDB | None = None
        with contextlib.suppress(ComputationalRunNotFoundError):
            last_run = await comp_runs_repo.get(
                user_id=computation.user_id, project_id=computation.project_id
            )

        return ComputationGet(
            id=computation.project_id,
            state=pipeline_state,
            pipeline_details=await compute_pipeline_details(
                complete_dag, minimal_computational_dag, comp_tasks
            ),
            url=TypeAdapter(AnyHttpUrl).validate_python(
                f"{request.url}/{computation.project_id}?user_id={computation.user_id}",
            ),
            stop_url=(
                TypeAdapter(AnyHttpUrl).validate_python(
                    f"{request.url}/{computation.project_id}:stop?user_id={computation.user_id}",
                )
                if computation.start_pipeline
                else None
            ),
            iteration=last_run.iteration if last_run else None,
            cluster_id=last_run.cluster_id if last_run else None,
            result=None,
            started=compute_pipeline_started_timestamp(
                minimal_computational_dag, comp_tasks
            ),
            stopped=compute_pipeline_stopped_timestamp(
                minimal_computational_dag, comp_tasks
            ),
            submitted=compute_pipeline_submitted_timestamp(
                minimal_computational_dag, comp_tasks
            ),
        )

    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{e}") from e
    except ClusterNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=f"{e}"
        ) from e
    except PricingPlanUnitNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{e}") from e
    except ClustersKeeperNotAvailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"{e}"
        ) from e
    except ConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{e}"
        ) from e
    except WalletNotEnoughCreditsError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=f"{e}"
        ) from e


@router.get(
    "/{project_id}",
    summary="Returns a computation pipeline state",
    response_model=ComputationGet,
    status_code=status.HTTP_200_OK,
)
async def get_computation(
    user_id: UserID,
    project_id: ProjectID,
    request: Request,
    project_repo: Annotated[
        ProjectsRepository, Depends(get_repository(ProjectsRepository))
    ],
    comp_pipelines_repo: Annotated[
        CompPipelinesRepository, Depends(get_repository(CompPipelinesRepository))
    ],
    comp_tasks_repo: Annotated[
        CompTasksRepository, Depends(get_repository(CompTasksRepository))
    ],
    comp_runs_repo: Annotated[
        CompRunsRepository, Depends(get_repository(CompRunsRepository))
    ],
) -> ComputationGet:
    _logger.debug(
        "User %s getting computation status for project %s",
        f"{user_id=}",
        f"{project_id=}",
    )

    # check that project actually exists
    await project_repo.get_project(project_id)

    pipeline_dag, all_tasks, filtered_tasks = await analyze_pipeline(
        project_id, comp_pipelines_repo, comp_tasks_repo
    )

    pipeline_state: RunningState = utils.get_pipeline_state_from_task_states(
        filtered_tasks
    )

    _logger.debug(
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
    last_run: CompRunsAtDB | None = None
    with contextlib.suppress(ComputationalRunNotFoundError):
        last_run = await comp_runs_repo.get(user_id=user_id, project_id=project_id)

    self_url = request.url.remove_query_params("user_id")
    return ComputationGet(
        id=project_id,
        state=pipeline_state,
        pipeline_details=pipeline_details,
        url=TypeAdapter(AnyHttpUrl).validate_python(f"{request.url}"),
        stop_url=(
            TypeAdapter(AnyHttpUrl).validate_python(
                f"{self_url}:stop?user_id={user_id}"
            )
            if pipeline_state.is_running()
            else None
        ),
        iteration=last_run.iteration if last_run else None,
        cluster_id=last_run.cluster_id if last_run else None,
        result=None,
        started=compute_pipeline_started_timestamp(pipeline_dag, all_tasks),
        stopped=compute_pipeline_stopped_timestamp(pipeline_dag, all_tasks),
        submitted=compute_pipeline_submitted_timestamp(pipeline_dag, all_tasks),
    )


@router.post(
    "/{project_id}:stop",
    summary="Stops a computation pipeline",
    response_model=ComputationGet,
    status_code=status.HTTP_202_ACCEPTED,
)
async def stop_computation(
    computation_stop: ComputationStop,
    project_id: ProjectID,
    request: Request,
    project_repo: Annotated[
        ProjectsRepository, Depends(get_repository(ProjectsRepository))
    ],
    comp_pipelines_repo: Annotated[
        CompPipelinesRepository, Depends(get_repository(CompPipelinesRepository))
    ],
    comp_tasks_repo: Annotated[
        CompTasksRepository, Depends(get_repository(CompTasksRepository))
    ],
    comp_runs_repo: Annotated[
        CompRunsRepository, Depends(get_repository(CompRunsRepository))
    ],
) -> ComputationGet:
    _logger.debug(
        "User %s stopping computation for project %s",
        computation_stop.user_id,
        project_id,
    )
    try:
        # check the project exists
        await project_repo.get_project(project_id)
        # get the project pipeline
        pipeline_at_db: CompPipelineAtDB = await comp_pipelines_repo.get_pipeline(
            project_id
        )
        pipeline_dag: nx.DiGraph = pipeline_at_db.get_graph()
        # get the project task states
        tasks: list[CompTaskAtDB] = await comp_tasks_repo.list_tasks(project_id)
        # create the complete DAG graph
        complete_dag = create_complete_dag_from_tasks(tasks)
        # filter the tasks by the effective pipeline
        filtered_tasks = [
            t for t in tasks if f"{t.node_id}" in set(pipeline_dag.nodes())
        ]
        pipeline_state = utils.get_pipeline_state_from_task_states(filtered_tasks)

        if utils.is_pipeline_running(pipeline_state):
            await stop_pipeline(
                request.app, user_id=computation_stop.user_id, project_id=project_id
            )

        # get run details if any
        last_run: CompRunsAtDB | None = None
        with contextlib.suppress(ComputationalRunNotFoundError):
            last_run = await comp_runs_repo.get(
                user_id=computation_stop.user_id, project_id=project_id
            )

        return ComputationGet(
            id=project_id,
            state=pipeline_state,
            pipeline_details=await compute_pipeline_details(
                complete_dag, pipeline_dag, tasks
            ),
            url=TypeAdapter(AnyHttpUrl).validate_python(f"{request.url}"),
            stop_url=None,
            iteration=last_run.iteration if last_run else None,
            cluster_id=last_run.cluster_id if last_run else None,
            result=None,
            started=compute_pipeline_started_timestamp(pipeline_dag, tasks),
            stopped=compute_pipeline_stopped_timestamp(pipeline_dag, tasks),
            submitted=compute_pipeline_submitted_timestamp(pipeline_dag, tasks),
        )

    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{e}") from e
    except ComputationalSchedulerError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{e}") from e


@router.delete(
    "/{project_id}",
    summary="Deletes a computation pipeline",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_computation(
    computation_stop: ComputationDelete,
    project_id: ProjectID,
    request: Request,
    project_repo: Annotated[
        ProjectsRepository, Depends(get_repository(ProjectsRepository))
    ],
    comp_pipelines_repo: Annotated[
        CompPipelinesRepository, Depends(get_repository(CompPipelinesRepository))
    ],
    comp_tasks_repo: Annotated[
        CompTasksRepository, Depends(get_repository(CompTasksRepository))
    ],
) -> None:
    try:
        # get the project
        project: ProjectAtDB = await project_repo.get_project(project_id)
        # check if current state allow to stop the computation
        comp_tasks: list[CompTaskAtDB] = await comp_tasks_repo.list_computational_tasks(
            project_id
        )
        pipeline_state = utils.get_pipeline_state_from_task_states(comp_tasks)
        if utils.is_pipeline_running(pipeline_state):
            if not computation_stop.force:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Projet {project_id} is currently running and cannot be deleted, current state is {pipeline_state}",
                )
            # abort the pipeline first
            try:
                await stop_pipeline(
                    request.app, user_id=computation_stop.user_id, project_id=project_id
                )
            except ComputationalSchedulerError as e:
                _logger.warning(
                    "Project %s could not be stopped properly.\n reason: %s",
                    project_id,
                    e,
                )

            def return_last_value(retry_state: Any) -> Any:
                """return the result of the last call attempt"""
                return retry_state.outcome.result()

            @retry(
                stop=stop_after_delay(_PIPELINE_ABORT_TIMEOUT_S),
                wait=wait_random(0, 2),
                retry_error_callback=return_last_value,
                retry=retry_if_result(lambda result: result is False),
                reraise=False,
                before_sleep=before_sleep_log(_logger, logging.INFO),
            )
            async def check_pipeline_stopped() -> bool:
                comp_tasks: list[CompTaskAtDB] = (
                    await comp_tasks_repo.list_computational_tasks(project_id)
                )
                pipeline_state = utils.get_pipeline_state_from_task_states(
                    comp_tasks,
                )
                return utils.is_pipeline_stopped(pipeline_state)

            # wait for the pipeline to be stopped
            if not await check_pipeline_stopped():
                _logger.error(
                    "pipeline %s could not be stopped properly after %ss",
                    project_id,
                    _PIPELINE_ABORT_TIMEOUT_S,
                )

        # delete the pipeline now
        await comp_tasks_repo.delete_tasks_from_project(project.uuid)
        await comp_pipelines_repo.delete_pipeline(project_id)

    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{e}") from e
