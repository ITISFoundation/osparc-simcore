"""
    These tables were designed to be controled by projects-plugin in
    the webserver's service
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
from .projects_nodes import projects_nodes

projects_metadata = sa.Table(
    "projects_metadata",
    #
    # Keeps "third-party" metadata attached to a project
    #
    # CUSTOM metadata:
    #   These SHOULD NOT be actual properties of the project (e.g. uuid, name etc)
    #   but rather information attached by third-parties that "decorate" or qualify
    #   a project resource
    #
    # project genealogy:
    #   a project might be created via the public API, in which case it might be created
    #   1. directly, as usual
    #   2. via a parent project/node combination (think jupyter/sim4life job creating a bunch of jobs)
    #   3. via a parent project/node that ran as a computation ("3rd generation" project, there is no limits to the number of generations)
    #
    #   in cases 2., 3. the parent_project_uuid is the direct parent project, and parent_node_id is the direct node parent as
    #   a specific node is defined by a project AND a node (since node IDs are non unique)
    #
    #   in cases 2., 3. the root_parent_project_uuid is the very first parent project, and root_parent_node_id is the very first parent node
    #
    metadata,
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            projects.c.uuid,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_projects_metadata_project_uuid",
        ),
        nullable=False,
        primary_key=True,
        doc="The project unique identifier",
    ),
    sa.Column(
        "custom",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Reserved for the user to store custom metadata",
    ),
    sa.Column(
        "parent_project_uuid",
        sa.String,
        nullable=True,
        doc="If applicable the parent project UUID of this project (the node that ran the public API to start this project_uuid lives in a project with UUID parent_project_uuid)",
    ),
    sa.Column(
        "parent_node_id",
        sa.String,
        nullable=True,
        doc="If applicable the parent node UUID of this project (the node that ran the public API to start this project_uuid lives in a node with ID parent_node_id)",
    ),
    sa.Column(
        "root_parent_project_uuid",
        sa.String,
        nullable=True,
        doc="If applicable the root parent project UUID of this project (the root project UUID in which the root node created the very first child)",
    ),
    sa.Column(
        "root_parent_node_id",
        sa.String,
        nullable=True,
        doc="If applicable the root parent node UUID of this project (the root node ID of the node that created the very first child)",
    ),
    # TIME STAMPS ----ß
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.PrimaryKeyConstraint("project_uuid"),
    sa.ForeignKeyConstraint(
        ("parent_project_uuid", "parent_node_id"),
        (projects_nodes.c.project_uuid, projects_nodes.c.node_id),
        onupdate=RefActions.CASCADE,
        ondelete=RefActions.SET_NULL,
        name="fk_projects_metadata_parent_node_id",
    ),
    sa.ForeignKeyConstraint(
        ("root_parent_project_uuid", "root_parent_node_id"),
        (projects_nodes.c.project_uuid, projects_nodes.c.node_id),
        onupdate=RefActions.CASCADE,
        ondelete=RefActions.SET_NULL,
        name="fk_projects_metadata_root_parent_node_id",
    ),
)


register_modified_datetime_auto_update_trigger(projects_metadata)
