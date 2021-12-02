import asyncio
import collections
import logging
import traceback
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Final,
    Iterable,
    List,
    Optional,
    Tuple,
    Union,
    cast,
)
from uuid import uuid4

import distributed
from aiopg.sa.engine import Engine
from dask_task_models_library.container_tasks.events import (
    DaskTaskEvents,
    TaskStateEvent,
)
from dask_task_models_library.container_tasks.io import (
    FileUrl,
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from pydantic import AnyUrl
from servicelib.json_serialization import json_dumps
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports_v2 import links, port_utils

from ..core.errors import (
    ComputationalBackendNotConnectedError,
    InsuficientComputationalResourcesError,
    MissingComputationalResourcesError,
)
from ..models.domains.comp_tasks import Image
from ..models.schemas.constants import ClusterID, UserID
from ..models.schemas.services import NodeRequirements

logger = logging.getLogger(__name__)

ServiceKeyStr = str
ServiceVersionStr = str


def generate_dask_job_id(
    service_key: ServiceKeyStr,
    service_version: ServiceVersionStr,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
) -> str:
    """creates a dask job id:
    The job ID shall contain the user_id, project_id, node_id
    Also, it must be unique
    and it is shown in the Dask scheduler dashboard website
    """
    return f"{service_key}:{service_version}:userid_{user_id}:projectid_{project_id}:nodeid_{node_id}:uuid_{uuid4()}"


def parse_dask_job_id(
    job_id: str,
) -> Tuple[ServiceKeyStr, ServiceVersionStr, UserID, ProjectID, NodeID]:
    parts = job_id.split(":")
    assert len(parts) == 6  # nosec
    return (
        parts[0],
        parts[1],
        UserID(parts[2][len("userid_") :]),
        ProjectID(parts[3][len("projectid_") :]),
        NodeID(parts[4][len("nodeid_") :]),
    )


async def _create_node_ports(
    db_engine: Engine, user_id: UserID, project_id: ProjectID, node_id: NodeID
) -> node_ports_v2.Nodeports:
    db_manager = node_ports_v2.DBManager(db_engine)
    return await node_ports_v2.ports(
        user_id=user_id,
        project_id=f"{project_id}",
        node_uuid=f"{node_id}",
        db_manager=db_manager,
    )


async def parse_output_data(
    db_engine: Engine, job_id: str, data: TaskOutputData
) -> None:
    (
        service_key,
        service_version,
        user_id,
        project_id,
        node_id,
    ) = parse_dask_job_id(job_id)
    logger.debug(
        "parsing output %s of dask task for %s:%s of user %s on project '%s' and node '%s'",
        json_dumps(data, indent=2),
        service_key,
        service_version,
        user_id,
        project_id,
        node_id,
    )

    ports = await _create_node_ports(
        db_engine=db_engine,
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
    )
    for port_key, port_value in data.items():
        value_to_transfer: Optional[links.ItemValue] = None
        if isinstance(port_value, FileUrl):
            value_to_transfer = port_value.url
        else:
            value_to_transfer = port_value

        await (await ports.outputs)[port_key].set_value(value_to_transfer)


async def compute_input_data(
    app: FastAPI,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
) -> TaskInputData:
    ports = await _create_node_ports(
        db_engine=app.state.engine,
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
    )
    input_data = {}
    for port in (await ports.inputs).values():
        value_link = await port.get_value()
        if isinstance(value_link, AnyUrl):
            input_data[port.key] = FileUrl(
                url=value_link,
                file_mapping=(
                    next(iter(port.file_to_key_map)) if port.file_to_key_map else None
                ),
            )
        else:
            input_data[port.key] = value_link
    return TaskInputData.parse_obj(input_data)


async def compute_output_data_schema(
    app: FastAPI,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
) -> TaskOutputDataSchema:
    ports = await _create_node_ports(
        db_engine=app.state.engine,
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
    )
    output_data_schema = {}
    for port in (await ports.outputs).values():
        output_data_schema[port.key] = {"required": port.default_value is None}

        if port_utils.is_file_type(port.property_type):
            value_link = await port_utils.get_upload_link_from_storage(
                user_id=user_id,
                project_id=f"{project_id}",
                node_id=f"{node_id}",
                file_name=next(iter(port.file_to_key_map))
                if port.file_to_key_map
                else port.key,
            )
            output_data_schema[port.key].update(
                {
                    "mapping": next(iter(port.file_to_key_map))
                    if port.file_to_key_map
                    else None,
                    "url": value_link,
                }
            )

    return TaskOutputDataSchema.parse_obj(output_data_schema)


_LOGS_FILE_NAME = "logs.zip"


async def compute_service_log_file_upload_link(
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
) -> AnyUrl:

    value_link = await port_utils.get_upload_link_from_storage(
        user_id=user_id,
        project_id=f"{project_id}",
        node_id=f"{node_id}",
        file_name=_LOGS_FILE_NAME,
    )
    return value_link


UserCompleteCB = Callable[[TaskStateEvent], Awaitable[None]]

_DASK_FUTURE_TIMEOUT_S: Final[int] = 5


def done_dask_callback(
    dask_future: distributed.Future,
    task_to_future_map: Dict[str, distributed.Future],
    user_callback: UserCompleteCB,
    main_loop: asyncio.AbstractEventLoop,
):
    # NOTE: BEWARE we are called in a separate thread!!
    job_id = dask_future.key
    event_data: Optional[TaskStateEvent] = None
    logger.debug("task '%s' completed with status %s", job_id, dask_future.status)
    try:
        if dask_future.status == "error":
            task_exception = dask_future.exception(timeout=_DASK_FUTURE_TIMEOUT_S)
            task_traceback = dask_future.traceback(timeout=_DASK_FUTURE_TIMEOUT_S)
            event_data = TaskStateEvent(
                job_id=job_id,
                state=RunningState.FAILED,
                msg=json_dumps(
                    traceback.format_exception(
                        type(task_exception), value=task_exception, tb=task_traceback
                    )
                ),
            )
        elif dask_future.cancelled():
            event_data = TaskStateEvent(job_id=job_id, state=RunningState.ABORTED)
        else:
            task_result = cast(
                TaskOutputData, dask_future.result(timeout=_DASK_FUTURE_TIMEOUT_S)
            )
            assert task_result  # no sec
            event_data = TaskStateEvent(
                job_id=job_id,
                state=RunningState.SUCCESS,
                msg=task_result.json(),
            )
    except distributed.TimeoutError:
        event_data = TaskStateEvent(
            job_id=job_id,
            state=RunningState.FAILED,
            msg=f"Timeout error getting results of '{job_id}'",
        )
        logger.error(
            "fetching result of '%s' timed-out, please check",
            job_id,
            exc_info=True,
        )
    finally:
        # remove the future from the dict to remove any handle to the future, so the worker can free the memory
        task_to_future_map.pop(job_id)
        logger.debug("dispatching callback to finish task '%s'", job_id)
        assert event_data  # nosec
        try:
            asyncio.run_coroutine_threadsafe(user_callback(event_data), main_loop)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unexpected issue while transmitting state to main thread")


async def clean_task_output_and_log_files_if_invalid(
    db_engine: Engine, user_id: UserID, project_id: ProjectID, node_id: NodeID
) -> None:
    # check outputs
    node_ports = await _create_node_ports(db_engine, user_id, project_id, node_id)
    for port in (await node_ports.outputs).values():
        if not port_utils.is_file_type(port.property_type):
            continue
        file_name = (
            next(iter(port.file_to_key_map)) if port.file_to_key_map else port.key
        )
        if await port_utils.target_link_exists(
            user_id, f"{project_id}", f"{node_id}", file_name
        ):
            continue
        logger.debug("entry %s is invalid, cleaning...", port.key)
        await port_utils.delete_target_link(
            user_id, f"{project_id}", f"{node_id}", file_name
        )
    # check log file
    if not await port_utils.target_link_exists(
        user_id=user_id,
        project_id=f"{project_id}",
        node_id=f"{node_id}",
        file_name=_LOGS_FILE_NAME,
    ):
        await port_utils.delete_target_link(
            user_id, f"{project_id}", f"{node_id}", _LOGS_FILE_NAME
        )


async def dask_sub_consumer(
    task_event: DaskTaskEvents, handler: Callable[[str], Awaitable[None]]
):
    dask_sub = distributed.Sub(task_event.topic_name())
    async for dask_event in dask_sub:
        logger.debug(
            "received dask event '%s' of topic %s",
            dask_event,
            task_event.topic_name(),
        )
        await handler(dask_event)


async def dask_sub_consumer_task(
    task_event: DaskTaskEvents, handler: Callable[[str], Awaitable[None]]
):
    while True:
        try:
            logger.info(
                "starting consumer task for topic '%s'", task_event.topic_name()
            )
            await dask_sub_consumer(task_event, handler)
        except asyncio.CancelledError:
            logger.info("stopped consumer task for topic '%s'", task_event.topic_name())
            raise
        except Exception:  # pylint: disable=broad-except
            _REST_TIMEOUT_S: Final[int] = 1
            logger.exception(
                "unknown exception in consumer task for topic '%s', restarting task in %s sec...",
                task_event.topic_name(),
                _REST_TIMEOUT_S,
            )
            await asyncio.sleep(_REST_TIMEOUT_S)


def from_node_reqs_to_dask_resources(
    node_reqs: NodeRequirements,
) -> Dict[str, Union[int, float]]:
    """Dask resources are set such as {"CPU": X.X, "GPU": Y.Y, "RAM": INT}"""
    dask_resources = node_reqs.dict(exclude_unset=True, by_alias=True)
    logger.debug("transformed to dask resources: %s", dask_resources)
    return dask_resources


def check_client_can_connect_to_scheduler(client: distributed.Client):
    client_status = client.status
    if client_status not in "running":
        logger.error(
            "The computational backend is not connected!",
        )
        raise ComputationalBackendNotConnectedError()


def check_if_cluster_is_able_to_run_pipeline(
    node_id: NodeID,
    scheduler_info: Dict[str, Any],
    task_resources: Dict[str, Any],
    node_image: Image,
    cluster_id_prefix: str,
    cluster_id: ClusterID,
):
    logger.debug("Dask scheduler infos: %s", json_dumps(scheduler_info, indent=2))
    workers = scheduler_info.get("workers", {})

    def can_task_run_on_worker(
        task_resources: Dict[str, Any], worker_resources: Dict[str, Any]
    ) -> bool:
        def gen_check(
            task_resources: Dict[str, Any], worker_resources: Dict[str, Any]
        ) -> Iterable[bool]:
            for r in task_resources:
                yield worker_resources.get(r, 0) >= task_resources[r]

        return all(gen_check(task_resources, worker_resources))

    def cluster_missing_resources(
        task_resources: Dict[str, Any], cluster_resources: Dict[str, Any]
    ) -> List[str]:
        return [r for r in task_resources if r not in cluster_resources]

    cluster_resources_counter = collections.Counter()
    can_a_worker_run_task = False
    for worker in workers:
        worker_resources = workers[worker].get("resources", {})
        if worker_resources.get(f"{cluster_id_prefix}{cluster_id}"):
            cluster_resources_counter.update(worker_resources)
            if can_task_run_on_worker(task_resources, worker_resources):
                can_a_worker_run_task = True
    all_available_resources_in_cluster = dict(cluster_resources_counter)

    logger.debug(
        "Dask scheduler total available resources in cluster %s: %s, task needed resources %s",
        cluster_id,
        json_dumps(all_available_resources_in_cluster, indent=2),
        json_dumps(task_resources, indent=2),
    )

    if can_a_worker_run_task:
        return

    # check if we have missing resources
    if missing_resources := cluster_missing_resources(
        task_resources, all_available_resources_in_cluster
    ):
        raise MissingComputationalResourcesError(
            node_id=node_id,
            msg=f"Service {node_image.name}:{node_image.tag} cannot be scheduled "
            f"on cluster {cluster_id}: task needs '{task_resources}', "
            f"cluster has '{all_available_resources_in_cluster}', missing: '{missing_resources}'",
        )

    # well then our workers are not powerful enough
    raise InsuficientComputationalResourcesError(
        node_id=node_id,
        msg=f"Service {node_image.name}:{node_image.tag} cannot be scheduled "
        f"on cluster {cluster_id}: insuficient resources"
        f"cluster has '{all_available_resources_in_cluster}', missing: '{missing_resources}'",
    )
