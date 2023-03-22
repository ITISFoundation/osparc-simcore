import asyncio
import collections
import logging
from typing import Any, Awaitable, Callable, Final, Iterable, Optional, Union, get_args
from uuid import uuid4

import distributed
from aiopg.sa.engine import Engine
from dask_task_models_library.container_tasks.io import (
    FileUrl,
    PortValue,
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from fastapi import FastAPI
from models_library.clusters import ClusterID
from models_library.errors import ErrorDict
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import AnyUrl, ByteSize, ValidationError
from servicelib.json_serialization import json_dumps
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports_common.exceptions import (
    S3InvalidPathError,
    StorageInvalidCall,
)
from simcore_sdk.node_ports_v2 import FileLinkType, Port, links, port_utils
from simcore_sdk.node_ports_v2.links import ItemValue as _NPItemValue

from ..core.errors import (
    ComputationalBackendNotConnectedError,
    ComputationalSchedulerChangedError,
    InsuficientComputationalResourcesError,
    MissingComputationalResourcesError,
    PortsValidationError,
)
from ..models.domains.comp_tasks import Image
from ..models.schemas.services import NodeRequirements

logger = logging.getLogger(__name__)

ServiceKeyStr = str
ServiceVersionStr = str

_PVType = Optional[_NPItemValue]

assert len(get_args(_PVType)) == len(  # nosec
    get_args(PortValue)
), "Types returned by port.get_value() -> _PVType MUST map one-to-one to PortValue. See compute_input_data"


def _get_port_validation_errors(port_key: str, err: ValidationError) -> list[ErrorDict]:
    errors = err.errors()
    for error in errors:
        assert error["loc"][-1] != (port_key,)
        error["loc"] = error["loc"] + (port_key,)
    return errors


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
) -> tuple[ServiceKeyStr, ServiceVersionStr, UserID, ProjectID, NodeID]:
    parts = job_id.split(":")
    assert len(parts) == 6  # nosec
    return (
        parts[0],
        parts[1],
        UserID(parts[2][len("userid_") :]),
        ProjectID(parts[3][len("projectid_") :]),
        NodeID(parts[4][len("nodeid_") :]),
    )


async def create_node_ports(
    db_engine: Engine, user_id: UserID, project_id: ProjectID, node_id: NodeID
) -> node_ports_v2.Nodeports:
    """
    This function create a nodeports object by fetching the node state from the database
    and then validating all the ports.

    In some scenarios there is no need to redo this and therefore the returned instance
    can be passed and reused since members functions fetch the latest state from the database
    without having to go through the entire construction+validation process.

    For that reason, many of the functions below offer an optional `ports` parameter

    :raises PortsValidationError: if any of the ports assigned values are invalid
    """
    try:
        db_manager = node_ports_v2.DBManager(db_engine)
        return await node_ports_v2.ports(
            user_id=user_id,
            project_id=f"{project_id}",
            node_uuid=f"{node_id}",
            db_manager=db_manager,
        )
    except ValidationError as err:
        raise PortsValidationError(project_id, node_id, err.errors()) from err


async def parse_output_data(
    db_engine: Engine,
    job_id: str,
    data: TaskOutputData,
    ports: Optional[node_ports_v2.Nodeports] = None,
) -> None:
    """

    :raises PortsValidationError
    """
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

    if ports is None:
        ports = await create_node_ports(
            db_engine=db_engine,
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
        )

    ports_errors = []
    for port_key, port_value in data.items():
        value_to_transfer: Optional[links.ItemValue] = None
        if isinstance(port_value, FileUrl):
            value_to_transfer = port_value.url
        else:
            value_to_transfer = port_value

        try:
            await (await ports.outputs)[port_key].set_value(value_to_transfer)
        except ValidationError as err:
            ports_errors.extend(_get_port_validation_errors(port_key, err))

    if ports_errors:
        raise PortsValidationError(project_id, node_id, ports_errors)


async def compute_input_data(
    app: FastAPI,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    file_link_type: FileLinkType,
    ports: Optional[node_ports_v2.Nodeports] = None,
) -> TaskInputData:
    """Retrieves values registered to the inputs of project_id/node_id

    - ports is optional because

    :raises PortsValidationError: when inputs ports validation fail
    """

    if ports is None:
        ports = await create_node_ports(
            db_engine=app.state.engine,
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
        )

    input_data = {}

    ports_errors = []
    port: Port
    for port in (await ports.inputs).values():
        try:
            value: _PVType = await port.get_value(file_link_type=file_link_type)

            # Mapping _PVType -> PortValue
            if isinstance(value, AnyUrl):
                logger.debug("Creating file url for %s", f"{port=}")
                input_data[port.key] = FileUrl(
                    url=value,
                    file_mapping=(
                        next(iter(port.file_to_key_map))
                        if port.file_to_key_map
                        else None
                    ),
                    file_mime_type=port.property_type.removeprefix("data:"),
                )
            else:
                input_data[port.key] = value

        except ValidationError as err:
            ports_errors.extend(_get_port_validation_errors(port.key, err))

    if ports_errors:
        raise PortsValidationError(project_id, node_id, ports_errors)

    return TaskInputData.parse_obj(input_data)


async def compute_output_data_schema(
    app: FastAPI,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    file_link_type: FileLinkType,
    ports: Optional[node_ports_v2.Nodeports] = None,
) -> TaskOutputDataSchema:
    """

    :raises PortsValidationError
    """
    if ports is None:
        # Based on when this function is normally called,
        # it is very unlikely that NodePorts raise an exception here
        # This function only needs the outputs but the design of NodePorts
        # will validate all inputs and outputs.
        ports = await create_node_ports(
            db_engine=app.state.engine,
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
        )

    output_data_schema = {}
    for port in (await ports.outputs).values():
        output_data_schema[port.key] = {"required": port.default_value is None}

        if port_utils.is_file_type(port.property_type):
            value_links = await port_utils.get_upload_links_from_storage(
                user_id=user_id,
                project_id=f"{project_id}",
                node_id=f"{node_id}",
                file_name=next(iter(port.file_to_key_map))
                if port.file_to_key_map
                else port.key,
                link_type=file_link_type,
                file_size=ByteSize(0),  # will create a single presigned link
            )
            assert value_links.urls  # nosec
            assert len(value_links.urls) == 1  # nosec
            output_data_schema[port.key].update(
                {
                    "mapping": next(iter(port.file_to_key_map))
                    if port.file_to_key_map
                    else None,
                    "url": f"{value_links.urls[0]}",
                }
            )

    return TaskOutputDataSchema.parse_obj(output_data_schema)


_LOGS_FILE_NAME = "logs.zip"


async def compute_service_log_file_upload_link(
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    file_link_type: FileLinkType,
) -> AnyUrl:
    value_links = await port_utils.get_upload_links_from_storage(
        user_id=user_id,
        project_id=f"{project_id}",
        node_id=f"{node_id}",
        file_name=_LOGS_FILE_NAME,
        link_type=file_link_type,
        file_size=ByteSize(0),  # will create a single presigned link
    )
    return value_links.urls[0]


async def get_service_log_file_download_link(
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    file_link_type: FileLinkType,
) -> Optional[AnyUrl]:
    """Returns None if log file is not available (e.g. when tasks is not done)

    : raises StorageServerIssue
    : raises NodeportsException
    """
    try:
        value_link = await port_utils.get_download_link_from_storage_overload(
            user_id=user_id,
            project_id=f"{project_id}",
            node_id=f"{node_id}",
            file_name=_LOGS_FILE_NAME,
            link_type=file_link_type,
        )
        return value_link

    except (S3InvalidPathError, StorageInvalidCall) as err:
        logger.debug("Log for task %s not found: %s", f"{project_id=}/{node_id=}", err)
        return None


async def clean_task_output_and_log_files_if_invalid(
    db_engine: Engine,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    ports: Optional[node_ports_v2.Nodeports] = None,
) -> None:
    """

    :raises PortsValidationError: when output ports validation fail
    """

    # check outputs
    if ports is None:
        ports = await create_node_ports(db_engine, user_id, project_id, node_id)

    for port in (await ports.outputs).values():
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
    dask_sub: distributed.Sub,
    handler: Callable[[str], Awaitable[None]],
):
    async for dask_event in dask_sub:
        logger.debug(
            "received dask event '%s' of topic %s",
            dask_event,
            dask_sub.name,
        )
        await handler(dask_event)
        await asyncio.sleep(0.010)


async def dask_sub_consumer_task(
    dask_sub: distributed.Sub,
    handler: Callable[[str], Awaitable[None]],
):
    while True:
        try:
            logger.info("starting dask consumer task for topic '%s'", dask_sub.name)
            await dask_sub_consumer(dask_sub, handler)
        except asyncio.CancelledError:
            logger.info("stopped dask consumer task for topic '%s'", dask_sub.name)
            raise
        except Exception:  # pylint: disable=broad-except
            _REST_TIMEOUT_S: Final[int] = 1
            logger.exception(
                "unknown exception in dask consumer task for topic '%s', restarting task in %s sec...",
                dask_sub.name,
                _REST_TIMEOUT_S,
            )
            await asyncio.sleep(_REST_TIMEOUT_S)


def from_node_reqs_to_dask_resources(
    node_reqs: NodeRequirements,
) -> dict[str, Union[int, float]]:
    """Dask resources are set such as {"CPU": X.X, "GPU": Y.Y, "RAM": INT}"""
    dask_resources = node_reqs.dict(
        exclude_unset=True,
        by_alias=True,
        exclude_none=True,
    )
    logger.debug("transformed to dask resources: %s", dask_resources)
    return dask_resources


def check_scheduler_is_still_the_same(
    original_scheduler_id: str, client: distributed.Client
):
    logger.debug("current %s", f"{client.scheduler_info()=}")
    if "id" not in client.scheduler_info():
        raise ComputationalSchedulerChangedError(
            original_scheduler_id=original_scheduler_id,
            current_scheduler_id="No scheduler identifier",
        )
    current_scheduler_id = client.scheduler_info()["id"]
    if current_scheduler_id != original_scheduler_id:
        logger.error("The computational backend changed!")
        raise ComputationalSchedulerChangedError(
            original_scheduler_id=original_scheduler_id,
            current_scheduler_id=current_scheduler_id,
        )


def check_communication_with_scheduler_is_open(client: distributed.Client):
    if (
        client.scheduler_comm
        and client.scheduler_comm.comm is not None
        and client.scheduler_comm.comm.closed()
    ):
        raise ComputationalBackendNotConnectedError()


def check_scheduler_status(client: distributed.Client):
    client_status = client.status
    if client_status not in "running":
        logger.error(
            "The computational backend is not connected!",
        )
        raise ComputationalBackendNotConnectedError()


def check_if_cluster_is_able_to_run_pipeline(
    project_id: ProjectID,
    node_id: NodeID,
    scheduler_info: dict[str, Any],
    task_resources: dict[str, Any],
    node_image: Image,
    cluster_id: ClusterID,
):
    logger.debug("Dask scheduler infos: %s", json_dumps(scheduler_info, indent=2))
    workers = scheduler_info.get("workers", {})

    def can_task_run_on_worker(
        task_resources: dict[str, Any], worker_resources: dict[str, Any]
    ) -> bool:
        def gen_check(
            task_resources: dict[str, Any], worker_resources: dict[str, Any]
        ) -> Iterable[bool]:
            for name, required_value in task_resources.items():
                if required_value is None:
                    yield True
                elif worker_has := worker_resources.get(name):
                    yield worker_has >= required_value
                else:
                    yield False

        return all(gen_check(task_resources, worker_resources))

    def cluster_missing_resources(
        task_resources: dict[str, Any], cluster_resources: dict[str, Any]
    ) -> list[str]:
        return [r for r in task_resources if r not in cluster_resources]

    cluster_resources_counter = collections.Counter()
    can_a_worker_run_task = False
    for worker in workers:
        worker_resources = workers[worker].get("resources", {})
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
        cluster_resources = (
            f"'{all_available_resources_in_cluster}', missing: '{missing_resources}'"
            if all_available_resources_in_cluster
            else "no workers available! TIP: contact oSparc support"
        )

        raise MissingComputationalResourcesError(
            project_id=project_id,
            node_id=node_id,
            msg=f"Service {node_image.name}:{node_image.tag} cannot be scheduled "
            f"on cluster {cluster_id}: task needs '{task_resources}', "
            f"cluster has {cluster_resources}",
        )

    # well then our workers are not powerful enough
    raise InsuficientComputationalResourcesError(
        project_id=project_id,
        node_id=node_id,
        msg=f"Service {node_image.name}:{node_image.tag} cannot be scheduled "
        f"on cluster {cluster_id}: insuficient resources"
        f"cluster has '{all_available_resources_in_cluster}', cluster has no worker with the"
        " necessary computational resources for running the service! TIP: contact oSparc support",
    )
