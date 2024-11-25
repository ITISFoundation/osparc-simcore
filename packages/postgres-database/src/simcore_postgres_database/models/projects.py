""" Projects table

"""
import enum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.sql import expression, func

from ._common import RefActions
from .base import metadata


class ProjectType(enum.Enum):
    """
    template: template project
    standard: standard project
    """

    TEMPLATE = "TEMPLATE"
    STANDARD = "STANDARD"


projects = sa.Table(
    "projects",
    metadata,
    sa.Column(
        "id", sa.BigInteger, nullable=False, primary_key=True, doc="Identifier index"
    ),
    sa.Column(
        "type",
        sa.Enum(ProjectType),
        nullable=False,
        default=ProjectType.STANDARD,
        doc="Either standard or template types",
    ),
    sa.Column(
        "uuid",
        sa.String,
        nullable=False,
        unique=True,
        doc="Unique global identifier",
    ),
    sa.Column(
        "name",
        sa.String,
        nullable=False,
        doc="Display name",
    ),
    sa.Column(
        "description",
        sa.String,
        nullable=True,
        doc="Markdown-compatible display description",
    ),
    sa.Column(
        "thumbnail",
        sa.String,
        nullable=True,
        doc="Link to thumbnail image",
    ),
    sa.Column(
        "prj_owner",
        sa.BigInteger,
        sa.ForeignKey(
            "users.id",
            name="fk_projects_prj_owner_users",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.RESTRICT,
        ),
        nullable=True,
        doc="Project's owner",
        index=True,
    ),
    sa.Column(
        "creation_date",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp on creation",
    ),
    sa.Column(
        "last_change_date",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp with last update",
    ),
    sa.Column(
        "access_rights",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Read/write/delete access rights of each group (gid) on this project",
    ),
    sa.Column(
        "workbench",
        sa.JSON,
        nullable=False,
        doc="Pipeline with the project's workflow. Schema in models_library.projects.Workbench",
    ),
    sa.Column(
        "ui",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="UI components. Schema in models_library.projects_ui",
    ),
    sa.Column(
        "classifiers",
        ARRAY(sa.String, dimensions=1),
        nullable=False,
        server_default="{}",  # NOTE: I found this strange but https://stackoverflow.com/questions/30933266/empty-array-as-postgresql-array-column-default-value
        doc="A list of standard labels to classify this project",
    ),
    sa.Column(
        "dev",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Free JSON to use as sandbox. Development only",
    ),
    sa.Column(
        "quality",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Free JSON with quality assesment based on TSR",
    ),
    sa.Column(
        "published",
        sa.Boolean,
        nullable=False,
        default=False,
        doc="If true, the project is publicaly accessible via the studies dispatcher (i.e. no registration required)",
    ),
    sa.Column(
        "hidden",
        sa.Boolean,
        nullable=False,
        default=False,
        doc="If true, the project is by default not listed in the API",
    ),
    sa.Column(
        "trashed_at",
        sa.DateTime(timezone=True),
        nullable=True,
        comment="The date and time when the project was marked as trashed. "
        "Null if the project has not been trashed [default].",
    ),
    sa.Column(
        "trashed_explicitly",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        comment="Indicates whether the project was explicitly trashed by the user (true)"
        " or inherited its trashed status from a parent (false) [default].",
    ),
    sa.Column(
        "workspace_id",
        sa.BigInteger,
        sa.ForeignKey(
            "workspaces.workspace_id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_projects_to_workspaces_id",
        ),
        nullable=True,
        default=None,
    ),
)


# ------------------------ TRIGGERS
new_project_trigger = sa.DDL(
    """
DROP TRIGGER IF EXISTS project_creation on projects;
CREATE TRIGGER project_creation
AFTER INSERT ON projects
    FOR EACH ROW
    EXECUTE PROCEDURE set_project_to_owner_group();
"""
)


# --------------------------- PROCEDURES
assign_project_access_rights_to_owner_group_procedure = sa.DDL(
    """
CREATE OR REPLACE FUNCTION set_project_to_owner_group() RETURNS TRIGGER AS $$
DECLARE
    group_id BIGINT;
BEGIN
    -- Fetch the group_id based on the owner from the other table
    SELECT u.primary_gid INTO group_id
    FROM users u
    WHERE u.id = NEW.prj_owner
    LIMIT 1;

    IF group_id IS NOT NULL THEN
        IF TG_OP = 'INSERT' THEN
            INSERT INTO "project_to_groups" ("gid", "project_uuid", "read", "write", "delete") VALUES (group_id, NEW.uuid, TRUE, TRUE, TRUE);
        END IF;
    END IF;
    RETURN NULL;
END; $$ LANGUAGE 'plpgsql';
    """
)

sa.event.listen(
    projects, "after_create", assign_project_access_rights_to_owner_group_procedure
)
sa.event.listen(
    projects,
    "after_create",
    new_project_trigger,
)
