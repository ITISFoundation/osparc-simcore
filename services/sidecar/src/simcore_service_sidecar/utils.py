import asyncio
import logging
import aiodocker
from typing import List

import aiopg
import networkx as nx
from simcore_postgres_database.sidecar_models import SUCCESS, comp_pipeline, comp_tasks
from sqlalchemy import and_
from simcore_sdk.config.rabbit import Config as RabbitConfig
from celery import Celery

logger = logging.getLogger(__name__)


def wrap_async_call(fct: asyncio.coroutine):
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

    async def async_is_gpu_node():
        cmd = "grep -o -P -m1 'docker.*\K[0-9a-f]{64,}' /proc/self/cgroup"  # pylint: disable=anomalous-backslash-in-string
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )

        stdout, _ = await proc.communicate()
        container_id = stdout.decode("utf-8").strip()

        docker = aiodocker.Docker()

        container = await docker.containers.get(container_id)
        container_info = await container.show()
        node_id = container_info["Config"]["Labels"]["com.docker.swarm.node.id"]
        node_info = await docker.nodes.inspect(node_id=node_id)

        generic_resources = (
            node_info.get("Description", {})
            .get("Resources", {})
            .get("GenericResources", [])
        )

        has_gpu_support = False
        for entry in generic_resources:
            if entry["DiscreteResourceSpec"]["Kind"] == "VRAM":
                has_gpu_support = True
                break

        await docker.close()

        logger.info("Node GPU support: %s", has_gpu_support)
        return has_gpu_support

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
