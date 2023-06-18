""" Groups table

    - List of groups in the framework
    - Groups have a ID, name and a list of users that belong to the group
"""


import sqlalchemy as sa

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata
from .projects import projects
from .projects_nodes import projects_nodes

projects_to_projects_nodes = sa.Table(
    "projects_to_projects_nodes",
    metadata,
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            projects.c.uuid,
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_projects_to_projects_nodes_to_projects_uuid",
        ),
        doc="The project unique identifier",
    ),
    sa.Column(
        "node_id",
        sa.String,
        sa.ForeignKey(
            projects_nodes.c.node_id,
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_projects_to_projects_nodes_to_projects_nodes_node_id",
        ),
        doc="The node unique identifier",
    ),
    # TIME STAMPS ----
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.UniqueConstraint("project_uuid", "node_id"),
)


register_modified_datetime_auto_update_trigger(projects_to_projects_nodes)
