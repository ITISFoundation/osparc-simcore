""" Projects table

"""
import enum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.sql import func

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
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=True,
        doc="Project's owner",
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
)
