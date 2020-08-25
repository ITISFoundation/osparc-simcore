import asyncio
import logging
import uuid
from typing import Awaitable, List

import aiodocker
from aiopg.sa.result import RowProxy
import networkx as nx
from aiodocker.volumes import DockerVolume
from aiopg.sa import SAConnection
from sqlalchemy import and_

from celery import Celery
from simcore_postgres_database.sidecar_models import SUCCESS, comp_tasks
from simcore_sdk.config.rabbit import Config as RabbitConfig
from simcore_service_sidecar import config
from simcore_service_sidecar.mpi_lock import acquire_mpi_lock

from .exceptions import SidecarException

logger = logging.getLogger(__name__)


def wrap_async_call(fct: Awaitable):
    return asyncio.get_event_loop().run_until_complete(fct)


def find_entry_point(g: nx.DiGraph) -> List:
    result = []
    for node in g.nodes:
        if len(list(g.predecessors(node))) == 0:
            result.append(node)
    return result


async def is_node_ready(
    task: RowProxy,
    graph: nx.DiGraph,
    db_connection: SAConnection,
    _logger: logging.Logger,
) -> bool:
    query = comp_tasks.select().where(
        and_(
            comp_tasks.c.node_id.in_(list(graph.predecessors(task.node_id))),
            comp_tasks.c.project_id == task.project_id,
        )
    )
    result = await db_connection.execute(query)
    tasks = await result.fetchall()

    _logger.debug("TASK %s ready? Checking ..", task.internal_id)
    for dep_task in tasks:
        job_id = dep_task.job_id
        if not job_id:
            return False
        _logger.debug(
            "TASK %s DEPENDS ON %s with stat %s",
            task.internal_id,
            dep_task.internal_id,
            dep_task.state,
        )
        if not dep_task.state == SUCCESS:
            return False
    _logger.debug("TASK %s is ready", task.internal_id)
    return True


def execution_graph(pipeline: RowProxy) -> nx.DiGraph:
    d = pipeline.dag_adjacency_list
    G = nx.DiGraph()

    for node in d.keys():
        nodes = d[node]
        if len(nodes) == 0:
            G.add_node(node)
            continue
        G.add_edges_from([(node, n) for n in nodes])
    return G


def is_gpu_node() -> bool:
    """Returns True if this node has support to GPU,
    meaning that the `VRAM` label was added to it."""

    async def async_is_gpu_node() -> bool:
        async with aiodocker.Docker() as docker:
            spec_config = {
                "Cmd": "nvidia-smi",
                "Image": "nvidia/cuda:10.0-base",
                "AttachStdin": False,
                "AttachStdout": False,
                "AttachStderr": False,
                "Tty": False,
                "OpenStdin": False,
            }
            try:
                await docker.containers.run(
                    config=spec_config, name=f"sidecar_{uuid.uuid4()}_test_gpu"
                )
                return True
            except aiodocker.exceptions.DockerError as e:
                logger.warning("is_gpu_node DockerError during check: %s", str(e))

            return False

    has_gpu = wrap_async_call(async_is_gpu_node())
    logger.info("Node gpus support result %s", has_gpu)
    return has_gpu


def start_as_mpi_node() -> bool:
    """
    Checks if this node can be a taraget to start as an MPI node.
    If it can it will try to grab a Redlock, ensure it is the only service who can be
    started as MPI.
    """
    import subprocess

    command_output = subprocess.Popen(
        "cat /proc/cpuinfo | grep processor | wc -l", shell=True, stdout=subprocess.PIPE
    ).stdout.read()
    current_cpu_count: int = int(command_output)
    if current_cpu_count != config.TARGET_MPI_NODE_CPU_COUNT:
        return False

    # it the mpi_lock is acquired, this service must start as MPI node
    is_mpi_node = acquire_mpi_lock(current_cpu_count)
    return is_mpi_node


def assemble_celery_app(task_default_queue: str, rabbit_config: RabbitConfig) -> Celery:
    """Returns an instance of Celery using a different RabbitMQ queue"""
    app = Celery(
        rabbit_config.name,
        broker=rabbit_config.broker_url,
        backend=rabbit_config.backend,
    )
    app.conf.task_default_queue = task_default_queue
    return app


async def get_volume_mount_point(volume_name: str) -> str:
    try:
        docker_client: aiodocker.Docker = aiodocker.Docker()
        volume_attributes = await DockerVolume(docker_client, volume_name).show()
        return volume_attributes["Mountpoint"]

    except aiodocker.exceptions.DockerError as err:
        raise SidecarException(
            f"Error while retrieving docker volume {volume_name}"
        ) from err
    except KeyError as err:
        raise SidecarException(
            f"docker volume {volume_name} does not contain Mountpoint"
        ) from err
