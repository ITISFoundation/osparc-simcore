import uuid

import networkx as nx
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

UNKNOWN = 0
PENDING = 1
RUNNING = 2
SUCCESS = 3
FAILED = 4

class ComputationalPipeline(Base):
    __tablename__ = 'comp_pipeline'

    project_id = Column(String, primary_key=True, default=str(uuid.uuid4()))
    dag_adjacency_list = Column(JSON)
    state = Column(String, default=UNKNOWN)

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

class ComputationalTask(Base):
    __tablename__ = 'comp_tasks'
    # this task db id
    task_id = Column(Integer, primary_key=True)
    project_id = Column(String, ForeignKey('comp_pipeline.project_id'))
    # dag node id
    node_id = Column(String)
    # celery task id
    job_id = Column(String)
    # internal id (better for debugging, nodes from 1 to N)
    internal_id = Column(Integer)
    
    schema = Column(JSON)
    inputs = Column(JSON)
    outputs = Column(JSON)
    image = Column(JSON)
    state = Column(Integer, default=UNKNOWN)

    # utc timestamps for submission/start/end
    submit = Column(DateTime)
    start = Column(DateTime)
    end = Column(DateTime)
