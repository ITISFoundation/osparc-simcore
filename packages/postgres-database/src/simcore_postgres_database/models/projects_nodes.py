""" Groups table

    - List of groups in the framework
    - Groups have a ID, name and a list of users that belong to the group
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import (
    RefActions,
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata
from .projects import projects

projects_nodes = sa.Table(
    "projects_nodes",
    metadata,
    sa.Column(
        "project_node_id",
        sa.Integer,
        nullable=False,
        autoincrement=True,
        primary_key=True,
        doc="Project node index",
    ),
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            projects.c.uuid,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_projects_to_projects_nodes_to_projects_uuid",
        ),
        nullable=False,
        index=True,
        doc="The project unique identifier",
    ),
    sa.Column(
        "node_id",
        sa.String,
        nullable=False,
        index=True,
        doc="The node unique identifier",
    ),
    sa.Column(
        "required_resources",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="The node required resources",
    ),
    # TIME STAMPS ----
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.UniqueConstraint("project_uuid", "node_id"),
)


register_modified_datetime_auto_update_trigger(projects_nodes)
