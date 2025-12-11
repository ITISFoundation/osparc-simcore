"""Projects table"""

import enum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.sql import expression, func

from ._common import RefActions, column_trashed_by_user, column_trashed_datetime
from .base import metadata
from .users import users


class ProjectType(enum.Enum):
    TEMPLATE = "TEMPLATE"
    STANDARD = "STANDARD"


class ProjectTemplateType(str, enum.Enum):
    TEMPLATE = "TEMPLATE"
    TUTORIAL = "TUTORIAL"
    HYPERTOOL = "HYPERTOOL"


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
        "template_type",
        sa.Enum(ProjectTemplateType),
        nullable=True,
        default=None,
        doc="None if type is STANDARD, otherwise it is one of the ProjectTemplateType",
    ),
    sa.Column(
        "uuid",
        sa.String,
        nullable=False,
        unique=True,
        doc="Unique global identifier",
    ),
    # DISPLAY ----------------------------
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
    # OWNERSHIP ----------------------------
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
    # PARENTHOOD ----------------------------
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
    # CHILDREN/CONTENT--------------------------
    # NOTE: commented out to check who still uses this
    # sa.Column(
    #     "workbench",
    #     sa.JSON,
    #     nullable=False,
    #     doc="Pipeline with the project's workflow. Schema in models_library.projects.Workbench",
    # ),
    # FRONT-END ----------------------------
    sa.Column(
        "ui",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="UI components. Schema in models_library.projects_ui",
    ),
    sa.Column(
        "dev",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Free JSON to use as sandbox. Development only",
    ),
    # FLAGS ----------------------------
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
    # LIFECYCLE ----------------------------
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
    column_trashed_datetime("projects"),
    column_trashed_by_user("projects", users_table=users),
    sa.Column(
        "trashed_explicitly",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        comment="Indicates whether the project was explicitly trashed by the user (true)"
        " or inherited its trashed status from a parent (false) [default].",
    ),
    # TAGGING ----------------------------
    sa.Column(
        "classifiers",
        ARRAY(sa.String, dimensions=1),
        nullable=False,
        server_default="{}",
        # NOTE: I found this strange but
        # https://stackoverflow.com/questions/30933266/empty-array-as-postgresql-array-column-default-value
        doc="A list of standard labels to classify this project",
    ),
    sa.Column(
        "quality",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Free JSON with quality assesment based on TSR",
    ),
    # DEPRECATED ----------------------------
    sa.Column(
        "access_rights",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="DEPRECATED: Read/write/delete access rights of each group (gid) on this project",
    ),
    ### INDEXES ----------------------------
    sa.Index(
        "idx_projects_last_change_date_desc",
        sa.desc("last_change_date"),
    ),
)

# We define the partial index
sa.Index(
    "ix_projects_partial_type",
    projects.c.type,
    postgresql_where=(projects.c.type == ProjectType.TEMPLATE),
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
