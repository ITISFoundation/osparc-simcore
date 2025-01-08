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
        doc="Project unique identifier",
    ),
    sa.Column(
        "node_id",
        sa.String,
        nullable=False,
        index=True,
        doc="Node unique identifier",
    ),
    sa.Column(
        "required_resources",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Node required resources",
    ),
    # TIME STAMPS ----
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.Column(
        "key",
        sa.String,
        nullable=False,
        doc="Distinctive name for the node based on the docker registry path",
    ),
    sa.Column(
        "version",
        sa.String,
        nullable=False,
        doc="Semantic version number of the node",
    ),
    sa.Column(
        "label",
        sa.String,
        nullable=False,
        doc="Short name of the node",
    ),
    sa.Column(
        "progress",
        sa.Numeric,
        nullable=True,
        doc="Node progress value",
    ),
    sa.Column(
        "thumbnail",
        sa.String,
        nullable=True,
        doc="Url of the latest screenshot of the node",
    ),
    sa.Column(
        "input_access",
        JSONB,
        nullable=True,
        doc="Map with key - access level pairs",
    ),
    sa.Column(
        "input_nodes",
        JSONB,  # Array
        nullable=True,
        doc="Node IDs of where the node is connected to",
    ),
    sa.Column(
        "inputs",
        JSONB,
        nullable=True,
        doc="Input properties values",
    ),
    sa.Column(
        "inputs_units",
        JSONB,
        nullable=True,
        doc="Input unit values",
    ),
    sa.Column(
        "output_nodes",
        JSONB,  # Array
        nullable=True,
        doc="Node IDs of those connected to the output",
    ),
    sa.Column(
        "outputs",
        JSONB,
        nullable=True,
        doc="Output properties values",
    ),
    # sa.Column(
    #     "output_node",
    #     sa.BOOLEAN,
    #     nullable=True,
    #     doc="Deprecated",
    # ),
    sa.Column(
        "run_hash",
        sa.String,
        nullable=True,
        doc="HEX digest of the resolved inputs + outputs hash at the time when the last outputs were generated",
    ),
    sa.Column(
        "state",
        JSONB,
        nullable=True,
        doc="Node state",
    ),
    sa.Column(
        "parent",
        sa.String,
        nullable=True,
        doc="Parent's (group-nodes) node ID",
    ),
    # sa.Column(
    #     "position",
    #     JSONB,
    #     nullable=True,
    #     doc="Deprecated",
    # ),
    sa.Column(
        "boot_options",
        JSONB,
        nullable=True,
        doc="Some services provide alternative parameters to be injected at boot time."
        "The user selection should be stored here, and it will overwrite the services's defaults",
    ),
    sa.UniqueConstraint("project_uuid", "node_id"),
)


register_modified_datetime_auto_update_trigger(projects_nodes)
