import networkx as nx
from sqlalchemy.orm import mapper

from simcore_postgres_models.tables.comp_pipeline_table import comp_pipeline
from simcore_postgres_models.tables.comp_tasks_table import comp_tasks

from .base import metadata

# NOTE: All this file ises classical mapping to keep LEGACY
class Base:
    metadata = metadata


class ComputationalPipeline(object):
    #pylint: disable=no-member
    def __init__(self, **kargs):
        for key, value in kargs.items():
            setattr(self, key, value)

    @property
    def execution_graph(self):
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
        return '<id {}>'.format(self.id)

mapper(ComputationalPipeline, comp_pipeline)


class ComputationalTask(object):
    def __init__(self, **kargs):
        for key, value in kargs.items():
            setattr(self, key, value)


mapper(ComputationalTask, comp_tasks)


__all__ = [
    "metadata",
    "ComputationalPipeline",
    "ComputationalTask"
]
