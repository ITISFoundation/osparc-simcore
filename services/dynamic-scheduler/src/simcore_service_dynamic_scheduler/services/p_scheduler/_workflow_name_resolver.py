from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID

from ._models import WorkflowName


async def get_workflow_name_from_node_id(app: FastAPI, node_id: NodeID) -> WorkflowName:
    # transformers a node_id into a workflow name
    _ = app
    _ = node_id
    return "TODO: add implementation here"
