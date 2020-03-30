import asyncio
import logging
from typing import List

import aiopg
import networkx as nx
from simcore_postgres_database.sidecar_models import SUCCESS, comp_pipeline, comp_tasks
from sqlalchemy import and_


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
