# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any
from uuid import UUID

import pytest
from faker import Faker
from models_library.projects_nodes import Node
from simcore_postgres_database.utils_projects_nodes import (
    ProjectNode,
    ProjectNodeCreate,
)
from simcore_service_webserver.projects import _nodes_models_adapters

_NODE_DOMAIN_MODEL_DICT_EXAMPLES = Node.model_json_schema()["examples"]


@pytest.mark.parametrize(
    "node_data",
    _NODE_DOMAIN_MODEL_DICT_EXAMPLES,
    ids=[f"example-{i}" for i in range(len(_NODE_DOMAIN_MODEL_DICT_EXAMPLES))],
)
def test_adapters_between_different_node_models(node_data: dict[str, Any], faker: Faker):
    # dict -> to Node (from models_library)
    node_id = UUID(faker.uuid4())
    node = Node.model_validate(node_data)

    # Node -> ProjectNodeCreate (from simcore_postgres_database) using adapters
    project_node_create = _nodes_models_adapters.project_node_create_from_node(node, node_id)
    assert isinstance(project_node_create, ProjectNodeCreate)
    assert project_node_create.node_id == node_id

    # Node -> ProjectNode (from simcore_postgres_database) using adapters
    project_node = _nodes_models_adapters.project_node_from_node(
        node,
        node_id,
        created=faker.date_time(),
        modified=faker.date_time(),
    )

    assert isinstance(project_node, ProjectNode)
    assert project_node.node_id == node_id
    assert project_node.created != project_node.modified
    assert project_node_create.node_id == node_id

    # ProjectNodeCreate -> Node (from models_library) using adapters
    assert _nodes_models_adapters.node_from_project_node_create(project_node_create) == node

    # ProjectNode -> Node (from models_library) using adapters
    assert _nodes_models_adapters.node_from_project_node(project_node) == node
