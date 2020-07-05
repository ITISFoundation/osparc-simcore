import asyncio
import logging
import re
from typing import Awaitable, List

import aiopg
import networkx as nx
from sqlalchemy import and_

import aiodocker
from celery import Celery
from simcore_postgres_database.sidecar_models import SUCCESS, comp_pipeline, comp_tasks
from simcore_sdk.config.rabbit import Config as RabbitConfig

from .exceptions import MoreThenOneItemDetected

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
    task: comp_tasks,
    graph: nx.DiGraph,
    db_connection: aiopg.sa.SAConnection,
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


def execution_graph(pipeline: comp_pipeline) -> nx.DiGraph:
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

    def get_container_id_from_cgroup(cat_cgroup_content) -> str:
        """Parses the result of cat cat /proc/self/cgroup and returns a container_id or
        raises an error in case only one unique id was not found."""
        possible_candidates = {x for x in cat_cgroup_content.split() if len(x) >= 64}
        result_set = {x.split("/")[-1] for x in possible_candidates}
        if len(result_set) != 1:
            # pylint: disable=raising-format-tuple
            raise MoreThenOneItemDetected(
                "There should only be one entry in this set of possible container_ids"
                ", have a look at %s" % possible_candidates
            )
        return_value = result_set.pop()
        # check if length is 64 and all char match this regex [A-Fa-f0-9]
        if len(return_value) != 64 and re.findall("[A-Fa-f0-9]{64}", return_value):
            # pylint: disable=raising-format-tuple
            raise ValueError(
                "Found container ID is not a valid sha256 string %s", return_value
            )
        return return_value

    async def async_is_gpu_node() -> bool:
        docker = aiodocker.Docker()

        config = {
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
                config=config, name=f"sidecar_{os.getpid()}_test_gpu"
            )
            return True
        except aiodocker.exceptions.DockerError:
            pass
        return False

    return wrap_async_call(async_is_gpu_node())


def assemble_celery_app(task_default_queue: str, rabbit_config: RabbitConfig) -> Celery:
    """Returns an instance of Celery using a different RabbitMQ queue"""
    app = Celery(
        rabbit_config.name,
        broker=rabbit_config.broker_url,
        backend=rabbit_config.backend,
    )
    app.conf.task_default_queue = task_default_queue
    return app
