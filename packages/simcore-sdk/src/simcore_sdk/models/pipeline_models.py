# DEPRECATED: Use instead postgres-database
import networkx as nx
from simcore_postgres_database.models.comp_pipeline import StateType, comp_pipeline
from simcore_postgres_database.models.comp_tasks import comp_tasks
from sqlalchemy.orm import mapper

from .base import metadata


# NOTE: All this file ises classical mapping to keep LEGACY
class Base:
    metadata = metadata


class ComputationalPipeline:
    # pylint: disable=no-member
    def __init__(self, **kargs):
        for key, value in kargs.items():
            if key in ComputationalPipeline._sa_class_manager.keys():
                setattr(self, key, value)

    @property
    def execution_graph(self) -> nx.DiGraph:
        d = self.dag_adjacency_list
        G = nx.DiGraph()

        for node in d.keys():
            nodes = d[node]
            if len(nodes) == 0:
                G.add_node(node)
                continue
            G.add_edges_from([(node, n) for n in nodes])
        return G

    def __repr__(self):
        return "<id {}>".format(self.id)


mapper(ComputationalPipeline, comp_pipeline)


class ComputationalTask:
    # pylint: disable=no-member
    def __init__(self, **kargs):
        for key, value in kargs.items():
            if key in ComputationalTask._sa_class_manager.keys():
                setattr(self, key, value)


mapper(ComputationalTask, comp_tasks)


__all__ = [
    "metadata",
    "ComputationalPipeline",
    "ComputationalTask",
    "StateType",
]
