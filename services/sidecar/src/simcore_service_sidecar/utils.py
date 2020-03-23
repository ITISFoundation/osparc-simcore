import asyncio
from pathlib import Path
from typing import List

import networkx as nx
from sqlalchemy import and_, create_engine
from sqlalchemy.orm import sessionmaker

from simcore_sdk.config.db import Config as db_config
from simcore_sdk.models.pipeline_models import SUCCESS, ComputationalTask


def wrap_async_call(fct: asyncio.coroutine):
    return asyncio.get_event_loop().run_until_complete(fct)


def find_entry_point(g: nx.DiGraph) -> List:
    result = []
    for node in g.nodes:
        if len(list(g.predecessors(node))) == 0:
            result.append(node)
    return result


def is_node_ready(task, graph, _session, _logger):
    # pylint: disable=no-member
    tasks = (
        _session.query(ComputationalTask)
        .filter(
            and_(
                ComputationalTask.node_id.in_(list(graph.predecessors(task.node_id))),
                ComputationalTask.project_id == task.project_id,
            )
        )
        .all()
    )

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


class DbSettings:
    def __init__(self):
        self._db_config = db_config()
        self.db = create_engine(
            self._db_config.endpoint + f"?application_name={__name__}_{id(self)}",
            client_encoding="utf8",
            pool_pre_ping=True,
        )
        self.Session = sessionmaker(self.db, expire_on_commit=False)
        # self.session = self.Session()


class ExecutorSettings:
    def __init__(self):
        # shared folders
        self.in_dir: Path = ""
        self.out_dir: Path = ""
        self.log_dir: Path = ""
