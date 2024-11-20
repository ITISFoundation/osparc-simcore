import asyncio
import collections
import logging
from collections.abc import Awaitable, Callable, Coroutine, Generator
from typing import Any, Final, NoReturn, ParamSpec, TypeVar, cast
from uuid import uuid4

import dask_gateway  # type: ignore[import-untyped]
import distributed
from aiopg.sa.engine import Engine
from common_library.json_serialization import json_dumps
from dask_task_models_library.container_tasks.io import (
    FileUrl,
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from dask_task_models_library.container_tasks.protocol import (
    ContainerEnvsDict,
    ContainerLabelsDict,
    TaskOwner,
)
from fastapi import FastAPI
from models_library.api_schemas_directorv2.services import NodeRequirements
from models_library.clusters import ClusterID
from models_library.docker import DockerLabelKey, StandardSimcoreDockerLabels
from models_library.errors import ErrorDict
from models_library.projects import ProjectID, ProjectIDStr
from models_library.projects_nodes_io import NodeID, NodeIDStr
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import AnyUrl, ByteSize, TypeAdapter, ValidationError
from servicelib.logging_utils import log_catch, log_context
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports_common.exceptions import (
    S3InvalidPathError,
    StorageInvalidCall,
)
from simcore_sdk.node_ports_v2 import FileLinkType, Port, links, port_utils
from simcore_sdk.node_ports_v2.links import ItemValue as _NPItemValue

from ..constants import UNDEFINED_DOCKER_LABEL
from ..core.errors import (
    ComputationalBackendNotConnectedError,
    ComputationalSchedulerChangedError,
    InsuficientComputationalResourcesError,
    MissingComputationalResourcesError,
    PortsValidationError,
)
from ..models.comp_runs import ProjectMetadataDict, RunMetadataDict
from ..models.comp_tasks import Image
from ..models.dask_subsystem import DaskJobID
from ..modules.osparc_variables.substitutions import (
    resolve_and_substitute_session_variables_in_specs,
    substitute_vendor_secrets_in_specs,
)

_logger = logging.getLogger(__name__)

ServiceKeyStr = str
ServiceVersionStr = str

_PVType = _NPItemValue | None


def _get_port_validation_errors(port_key: str, err: ValidationError) -> list[ErrorDict]:
    errors = err.errors()
    for error in errors:
        assert error["loc"][-1] != (port_key,)
        error["loc"] = error["loc"] + (port_key,)
    return list(errors)


def generate_dask_job_id(
    service_key: ServiceKeyStr,
    service_version: ServiceVersionStr,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
) -> DaskJobID:
    """creates a dask job id:
    The job ID shall contain the user_id, project_id, node_id
    Also, it must be unique
    and it is shown in the Dask scheduler dashboard website
    """
    return DaskJobID(
        f"{service_key}:{service_version}:userid_{user_id}:projectid_{project_id}:nodeid_{node_id}:uuid_{uuid4()}"
    )


_JOB_ID_PARTS: Final[int] = 6


def parse_dask_job_id(
    job_id: str,
) -> tuple[ServiceKeyStr, ServiceVersionStr, UserID, ProjectID, NodeID]:
    parts = job_id.split(":")
    assert len(parts) == _JOB_ID_PARTS  # nosec
    return (
        parts[0],
        parts[1],
        TypeAdapter(UserID).validate_python(parts[2][len("userid_") :]),
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
            project_id=ProjectIDStr(f"{project_id}"),
            node_uuid=TypeAdapter(NodeIDStr).validate_python(f"{node_id}"),
            db_manager=db_manager,
        )
    except ValidationError as err:
        raise PortsValidationError(
            project_id=project_id, node_id=node_id, errors_list=list(err.errors())
        ) from err


async def parse_output_data(
    db_engine: Engine,
    job_id: str,
    data: TaskOutputData,
    ports: node_ports_v2.Nodeports | None = None,
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
    _logger.debug(
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
        value_to_transfer: links.ItemValue | None = None
        if isinstance(port_value, FileUrl):
            value_to_transfer = port_value.url
        else:
            value_to_transfer = port_value

        try:
            await (await ports.outputs)[port_key].set_value(value_to_transfer)
        except ValidationError as err:
            ports_errors.extend(_get_port_validation_errors(port_key, err))

    if ports_errors:
        raise PortsValidationError(
            project_id=project_id, node_id=node_id, errors_list=ports_errors
        )


async def compute_input_data(
    *,
    project_id: ProjectID,
    node_id: NodeID,
    file_link_type: FileLinkType,
    node_ports: node_ports_v2.Nodeports,
) -> TaskInputData:
    """Retrieves values registered to the inputs of project_id/node_id
    :raises PortsValidationError: when inputs ports validation fail
    """

    input_data: dict[str, Any] = {}

    ports_errors = []
    port: Port
    for port in (await node_ports.inputs).values():
        try:
            value: _PVType = await port.get_value(file_link_type=file_link_type)

            # Mapping _PVType -> PortValue
            if isinstance(value, AnyUrl):
                _logger.debug("Creating file url for %s", f"{port=}")
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
        raise PortsValidationError(
            project_id=project_id, node_id=node_id, errors_list=ports_errors
        )

    return TaskInputData.model_validate(input_data)


async def compute_output_data_schema(
    *,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    file_link_type: FileLinkType,
    node_ports: node_ports_v2.Nodeports,
) -> TaskOutputDataSchema:
    """

    :raises PortsValidationError
    """

    output_data_schema: dict[str, Any] = {}
    for port in (await node_ports.outputs).values():
        output_data_schema[port.key] = {"required": port.default_value is None}

        if port_utils.is_file_type(port.property_type):
            value_links = await port_utils.get_upload_links_from_storage(
                user_id=user_id,
                project_id=f"{project_id}",
                node_id=f"{node_id}",
                file_name=(
                    next(iter(port.file_to_key_map))
                    if port.file_to_key_map
                    else port.key
                ),
                link_type=file_link_type,
                file_size=ByteSize(0),  # will create a single presigned link
                sha256_checksum=None,
            )
            assert value_links.urls  # nosec
            assert len(value_links.urls) == 1  # nosec
            output_data_schema[port.key].update(
                {
                    "mapping": (
                        next(iter(port.file_to_key_map))
                        if port.file_to_key_map
                        else None
                    ),
                    "url": f"{value_links.urls[0]}",
                }
            )

    return TaskOutputDataSchema.model_validate(output_data_schema)


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
        sha256_checksum=None,
    )
    url: AnyUrl = value_links.urls[0]
    return url


def compute_task_labels(
    *,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    run_metadata: RunMetadataDict,
    node_requirements: NodeRequirements,
) -> ContainerLabelsDict:
    """
    Raises:
        ValidationError
    """
    product_name = run_metadata.get("product_name", UNDEFINED_DOCKER_LABEL)
    standard_simcore_labels = StandardSimcoreDockerLabels.model_construct(
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        product_name=product_name,
        simcore_user_agent=run_metadata.get(
            "simcore_user_agent", UNDEFINED_DOCKER_LABEL
        ),
        swarm_stack_name=UNDEFINED_DOCKER_LABEL,  # NOTE: there is currently no need for this label in the comp backend
        memory_limit=node_requirements.ram,
        cpu_limit=node_requirements.cpu,
    ).to_simcore_runtime_docker_labels()
    return standard_simcore_labels | TypeAdapter(ContainerLabelsDict).validate_python(
        {
            DockerLabelKey.from_key(k): f"{v}"
            for k, v in run_metadata.items()
            if k not in ["product_name", "simcore_user_agent"]
        },
    )


async def compute_task_envs(
    app: FastAPI,
    *,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    node_image: Image,
    metadata: RunMetadataDict,
) -> ContainerEnvsDict:
    product_name = metadata.get("product_name", UNDEFINED_DOCKER_LABEL)
    task_envs = node_image.envs
    if task_envs:
        vendor_substituted_envs = await substitute_vendor_secrets_in_specs(
            app,
            cast(dict[str, Any], node_image.envs),
            service_key=TypeAdapter(ServiceKey).validate_python(node_image.name),
            service_version=TypeAdapter(ServiceVersion).validate_python(node_image.tag),
            product_name=product_name,
        )
        resolved_envs = await resolve_and_substitute_session_variables_in_specs(
            app,
            vendor_substituted_envs,
            user_id=user_id,
            product_name=product_name,
            project_id=project_id,
            node_id=node_id,
        )
        # NOTE: see https://github.com/ITISFoundation/osparc-simcore/issues/3638
        # we currently do not validate as we are using illegal docker key names with underscores
        task_envs = cast(ContainerEnvsDict, resolved_envs)

    return task_envs


async def get_service_log_file_download_link(
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    file_link_type: FileLinkType,
) -> AnyUrl | None:
    """Returns None if log file is not available (e.g. when tasks is not done)

    : raises StorageServerIssue
    : raises NodeportsException
    """
    try:
        value_link: AnyUrl = await port_utils.get_download_link_from_storage_overload(
            user_id=user_id,
            project_id=f"{project_id}",
            node_id=f"{node_id}",
            file_name=_LOGS_FILE_NAME,
            link_type=file_link_type,
        )
        return value_link
    except (S3InvalidPathError, StorageInvalidCall) as err:
        _logger.debug("Log for task %s not found: %s", f"{project_id=}/{node_id=}", err)
        return None


async def clean_task_output_and_log_files_if_invalid(
    db_engine: Engine,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    ports: node_ports_v2.Nodeports | None = None,
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
        _logger.debug("entry %s is invalid, cleaning...", port.key)
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


async def _dask_sub_consumer(
    dask_sub: distributed.Sub,
    handler: Callable[[str], Awaitable[None]],
) -> None:
    async for dask_event in dask_sub:
        _logger.debug(
            "received dask event '%s' of topic %s",
            dask_event,
            dask_sub.name,
        )
        await handler(dask_event)


_REST_TIMEOUT_S: Final[int] = 1


async def dask_sub_consumer_task(
    dask_sub: distributed.Sub,
    handler: Callable[[str], Awaitable[None]],
) -> NoReturn:
    while True:
        with log_catch(_logger, reraise=False), log_context(
            _logger, level=logging.DEBUG, msg=f"dask sub task for topic {dask_sub.name}"
        ):
            await _dask_sub_consumer(dask_sub, handler)
        # we sleep a bit before restarting
        await asyncio.sleep(_REST_TIMEOUT_S)


def from_node_reqs_to_dask_resources(
    node_reqs: NodeRequirements,
) -> dict[str, int | float]:
    """Dask resources are set such as {"CPU": X.X, "GPU": Y.Y, "RAM": INT}"""
    dask_resources: dict[str, int | float] = node_reqs.model_dump(
        exclude_unset=True,
        by_alias=True,
        exclude_none=True,
    )
    _logger.debug("transformed to dask resources: %s", dask_resources)
    return dask_resources


def check_scheduler_is_still_the_same(
    original_scheduler_id: str, client: distributed.Client
):
    _logger.debug("current %s", f"{client.scheduler_info()=}")
    if "id" not in client.scheduler_info():
        raise ComputationalSchedulerChangedError(
            original_scheduler_id=original_scheduler_id,
            current_scheduler_id="No scheduler identifier",
        )
    current_scheduler_id = client.scheduler_info()["id"]
    if current_scheduler_id != original_scheduler_id:
        _logger.error("The computational backend changed!")
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
        raise ComputationalBackendNotConnectedError


def check_scheduler_status(client: distributed.Client):
    client_status = client.status
    if client_status not in "running":
        _logger.error(
            "The computational backend is not connected!",
        )
        raise ComputationalBackendNotConnectedError


_LARGE_NUMBER_OF_WORKERS: Final[int] = 10000


async def check_maximize_workers(cluster: dask_gateway.GatewayCluster | None) -> None:
    if cluster:
        await cluster.scale(_LARGE_NUMBER_OF_WORKERS)


def _can_task_run_on_worker(
    task_resources: dict[str, Any], worker_resources: dict[str, Any]
) -> bool:
    def gen_check(
        task_resources: dict[str, Any], worker_resources: dict[str, Any]
    ) -> Generator[bool, None, None]:
        for name, required_value in task_resources.items():
            if required_value is None:
                yield True
            elif worker_has := worker_resources.get(name):
                yield worker_has >= required_value
            else:
                yield False

    return all(gen_check(task_resources, worker_resources))


def _cluster_missing_resources(
    task_resources: dict[str, Any], cluster_resources: dict[str, Any]
) -> list[str]:
    return [r for r in task_resources if r not in cluster_resources]


def _to_human_readable_resource_values(resources: dict[str, Any]) -> dict[str, Any]:
    human_readable_resources = {}

    for res_name, res_value in resources.items():
        if "RAM" in res_name:
            try:
                human_readable_resources[res_name] = (
                    TypeAdapter(ByteSize).validate_python(res_value).human_readable()
                )
            except ValidationError:
                _logger.warning(
                    "could not parse %s:%s, please check what changed in how Dask prepares resources!",
                    f"{res_name=}",
                    res_value,
                )
                human_readable_resources[res_name] = res_value
        else:
            human_readable_resources[res_name] = res_value
    return human_readable_resources


def check_if_cluster_is_able_to_run_pipeline(
    project_id: ProjectID,
    node_id: NodeID,
    scheduler_info: dict[str, Any],
    task_resources: dict[str, Any],
    node_image: Image,
    cluster_id: ClusterID,
) -> None:

    _logger.debug(
        "Dask scheduler infos: %s", f"{scheduler_info}"
    )  # NOTE: be careful not to json_dumps this as it sometimes contain keys that are tuples!

    workers = scheduler_info.get("workers", {})

    cluster_resources_counter: collections.Counter = collections.Counter()
    can_a_worker_run_task = False
    for worker in workers:
        worker_resources = workers[worker].get("resources", {})
        cluster_resources_counter.update(worker_resources)
        if _can_task_run_on_worker(task_resources, worker_resources):
            can_a_worker_run_task = True
    all_available_resources_in_cluster = dict(cluster_resources_counter)

    _logger.debug(
        "Dask scheduler total available resources in cluster %s: %s, task needed resources %s",
        cluster_id,
        json_dumps(all_available_resources_in_cluster, indent=2),
        json_dumps(task_resources, indent=2),
    )

    if can_a_worker_run_task:  # OsparcErrorMixin
        return

    # check if we have missing resources
    if missing_resources := _cluster_missing_resources(
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
            service_name=node_image.name,
            service_version=node_image.tag,
            cluster_id=cluster_id,
            task_resources=task_resources,
            cluster_resources=cluster_resources,
        )

    # well then our workers are not powerful enough
    raise InsuficientComputationalResourcesError(
        project_id=project_id,
        node_id=node_id,
        service_name=node_image.name,
        service_version=node_image.tag,
        service_requested_resources=_to_human_readable_resource_values(task_resources),
        cluster_id=cluster_id,
        cluster_available_resources=[
            _to_human_readable_resource_values(worker.get("resources", None))
            for worker in workers.values()
        ],
    )


P = ParamSpec("P")
R = TypeVar("R")


async def wrap_client_async_routine(
    client_coroutine: Coroutine[Any, Any, Any] | Any | None
) -> Any:
    """Dask async behavior does not go well with Pylance as it returns
    a union of types. this wrapper makes both mypy and pylance happy"""
    assert client_coroutine  # nosec
    return await client_coroutine


def compute_task_owner(
    user_id: UserID,
    project_id: ProjectID,
    node_id: ProjectID,
    project_metadata: ProjectMetadataDict,
) -> TaskOwner:
    return TaskOwner(
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        parent_node_id=project_metadata.get("parent_node_id"),
        parent_project_id=project_metadata.get("parent_project_id"),
    )
