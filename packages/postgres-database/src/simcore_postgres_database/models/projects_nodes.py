""" Groups table

    - List of groups in the framework
    - Groups have a ID, name and a list of users that belong to the group
"""

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB

from ._common import (
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
        "node_id",
        sa.String,
        nullable=False,
        primary_key=True,
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
)


register_modified_datetime_auto_update_trigger(projects_nodes)


# TRIGGERS -----------------
projects_to_projects_nodes_deleted_trigger = sa.DDL(
    """
DROP TRIGGER IF EXISTS entry_deleted on projects;
CREATE TRIGGER entry_deleted
AFTER DELETE ON projects
FOR EACH ROW
EXECUTE FUNCTION delete_orphaned_project_nodes();
    """
)

# PROCEDURES -------------------
delete_orphaned_project_nodes_procedure = sa.DDL(
    """
CREATE OR REPLACE FUNCTION delete_orphaned_project_nodes()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM projects_nodes
    WHERE NOT EXISTS (
        SELECT 1 FROM projects_to_projects_nodes
        WHERE projects_to_projects_nodes.node_id = projects_nodes.node_id
    );
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
    """
)

# REGISTER THEM PROCEDURES/TRIGGERS


event.listen(projects_nodes, "after_create", delete_orphaned_project_nodes_procedure)
event.listen(projects, "after_create", projects_to_projects_nodes_deleted_trigger)
