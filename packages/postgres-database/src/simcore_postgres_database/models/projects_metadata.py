"""
    These tables were designed to be controled by projects-plugin in
    the webserver's service
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata
from .projects import projects
from .projects_nodes import projects_nodes

projects_metadata = sa.Table(
    "projects_metadata",
    #
    # Keeps "third-party" metadata attached to a project
    #
    # These SHOULD NOT be actual properties of the project (e.g. uuid, name etc)
    # but rather information attached by third-parties that "decorate" or qualify
    # a project resource
    #
    # Things like 'stars', 'quality', 'classifiers', 'dev', etc (or any kind of stats)
    # should be moved here
    #
    metadata,
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            projects.c.uuid,
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_projects_metadata_project_uuid",
        ),
        nullable=False,
        primary_key=True,
        doc="The project unique identifier is also used to identify the associated job",
    ),
    sa.Column(
        "parent_node_id",
        sa.String,
        sa.ForeignKey(
            projects_nodes.c.node_id,
            onupdate="CASCADE",
            ondelete="SET NULL",
            name="fk_projects_metadata_parent_node_id",
        ),
        nullable=True,
        doc="If applicable the parent node ID of this project",
    ),
    sa.Column(
        "custom",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Reserved for the user to store custom metadata",
    ),
    # TIME STAMPS ----ß
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.PrimaryKeyConstraint("project_uuid"),
)


register_modified_datetime_auto_update_trigger(projects_metadata)
