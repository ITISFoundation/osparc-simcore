""" Projects table

    - Every row fits a project document schemed as api/specs/webserver/v0/components/schemas/project-v0.0.1.json

"""
import enum
import logging

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.sql import func

from .base import metadata

log = logging.getLogger(__name__)


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
    sa.Column("id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column(
        "type", sa.Enum(ProjectType), nullable=False, default=ProjectType.STANDARD
    ),
    sa.Column("uuid", sa.String, nullable=False, unique=True),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("description", sa.String, nullable=True),
    sa.Column("thumbnail", sa.String, nullable=True),
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
    ),
    sa.Column(
        "creation_date", sa.DateTime(), nullable=False, server_default=func.now()
    ),
    sa.Column(
        "last_change_date",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),  # this will auto-update on modification
    ),
    sa.Column(
        "access_rights", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    ),
    sa.Column("workbench", sa.JSON, nullable=False),
    sa.Column("ui", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column(
        "classifiers",
        ARRAY(sa.String, dimensions=1),
        nullable=False,
        server_default="{}",
    ),
    sa.Column("dev", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("published", sa.Boolean, nullable=False, default=False),
)
