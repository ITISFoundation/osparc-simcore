import asyncio
import logging
from pprint import pformat
from typing import Awaitable, Callable, Dict, Optional, Tuple
from uuid import uuid4

import dask.distributed
from aiopg.sa.engine import Engine
from dask_task_models_library.container_tasks.events import TaskStateEvent
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
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports_v2 import links, port_utils

from ..models.schemas.constants import UserID

logger = logging.getLogger(__name__)


def generate_dask_job_id(
    service_key: str,
    service_version: str,
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


def parse_dask_job_id(job_id: str) -> Tuple[str, str, UserID, ProjectID, NodeID]:
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
    app: FastAPI, user_id: UserID, project_id: ProjectID, node_id: NodeID
) -> node_ports_v2.Nodeports:
    db_manager = node_ports_v2.DBManager(db_engine=app.state.engine)
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
        pformat(data),
        service_key,
        service_version,
        user_id,
        project_id,
        node_id,
    )

    db_manager = node_ports_v2.DBManager(db_engine=db_engine)
    ports = await node_ports_v2.ports(
        user_id=user_id,
        project_id=f"{project_id}",
        node_uuid=f"{node_id}",
        db_manager=db_manager,
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
        app=app, user_id=user_id, project_id=project_id, node_id=node_id
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
        app=app, user_id=user_id, project_id=project_id, node_id=node_id
    )
    output_data_schema = {}
    for port in (await ports.outputs).values():
        output_data_schema[port.key] = {"required": port.default_value is None}

        if port.property_type.startswith("data:"):
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


async def compute_service_log_file_upload_link(
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
) -> AnyUrl:
    LOGS_FILE_NAME = "logs.zip"
    value_link = await port_utils.get_upload_link_from_storage(
        user_id=user_id,
        project_id=f"{project_id}",
        node_id=f"{node_id}",
        file_name=LOGS_FILE_NAME,
    )
    return value_link


UserCompleteCB = Callable[[TaskStateEvent], Awaitable[None]]


def done_dask_callback(
    dask_future: dask.distributed.Future,
    task_to_future_map: Dict[str, dask.distributed.Future],
    user_callback: UserCompleteCB,
    main_loop: asyncio.AbstractEventLoop,
):
    # NOTE: BEWARE we are called in a separate thread!!
    job_id = dask_future.key
    event_data: Optional[TaskStateEvent] = None
    logger.debug("task '%s' completed with status %s", job_id, dask_future.status)
    try:
        if dask_future.status == "error":
            event_data = TaskStateEvent(
                job_id=job_id,
                state=RunningState.FAILED,
                msg=f"{dask_future.exception(timeout=5)}",
            )
        elif dask_future.cancelled():
            event_data = TaskStateEvent(job_id=job_id, state=RunningState.ABORTED)
        else:
            event_data = TaskStateEvent(
                job_id=job_id,
                state=RunningState.SUCCESS,
                msg=dask_future.result(timeout=5).json(),
            )
    except dask.distributed.TimeoutError:
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
        assert event_data  # no sec
        try:
            asyncio.run_coroutine_threadsafe(user_callback(event_data), main_loop)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unexpected issue while transmitting state to main thread")
