"""
Collection of free function adapters between Node-like pydantic models

- The tricky part here is to deal with alias in Node model which are not present in the DB models

"""

from datetime import datetime
from typing import Any
from uuid import UUID

from models_library.projects_nodes import Node
from simcore_postgres_database.utils_projects_nodes import (
    ProjectNode,
    ProjectNodeCreate,
)


def node_from_project_node_create(project_node_create: ProjectNodeCreate) -> Node:
    """
    Adapter: Converts a ProjectNodeCreate instance to a Node model.
    """
    exclude_fields = {"node_id", "required_resources"}

    assert set(ProjectNodeCreate.model_fields).issuperset(exclude_fields)  # nosec

    node_data: dict[str, Any] = project_node_create.model_dump(
        exclude=exclude_fields,
        exclude_none=True,
        exclude_unset=True,
    )
    return Node.model_validate(node_data, by_name=True)


def node_from_project_node(project_node: ProjectNode) -> Node:
    """
    Adapter: Converts a ProjectNode instance to a Node model.
    """
    exclude_fields = {"node_id", "required_resources", "created", "modified"}
    assert set(ProjectNode.model_fields).issuperset(exclude_fields)  # nosec

    node_data: dict[str, Any] = project_node.model_dump(
        exclude=exclude_fields,
        exclude_none=True,
        exclude_unset=True,
    )
    return Node.model_validate(node_data, by_name=True)


def project_node_create_from_node(node: Node, node_id: UUID) -> ProjectNodeCreate:
    """
    Adapter: Converts a Node model and node_id to a ProjectNodeCreate instance.
    """
    node_data: dict[str, Any] = node.model_dump(by_alias=False, mode="json")
    return ProjectNodeCreate(node_id=node_id, **node_data)


def project_node_from_node(
    node: Node, node_id: UUID, created: datetime, modified: datetime
) -> ProjectNode:
    """
    Adapter: Converts a Node model, node_id, created, and modified to a ProjectNode instance.
    """
    node_data: dict[str, Any] = node.model_dump(by_alias=False, mode="json")
    return ProjectNode(
        node_id=node_id,
        created=created,
        modified=modified,
        **node_data,
    )
