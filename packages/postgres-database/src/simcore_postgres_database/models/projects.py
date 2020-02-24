""" Projects table

    - Every row fits a project document schemed as api/specs/webserver/v0/components/schemas/project-v0.0.1.json

"""
import enum
import logging
from datetime import datetime

import sqlalchemy as sa

from .base import metadata

log = logging.getLogger(__name__)


class ProjectType(enum.Enum):
    """
        template: template project
        standard: standard project
    """

    TEMPLATE = "template"
    STANDARD = "standard"


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
    sa.Column("prj_owner", sa.String, nullable=False),
    sa.Column("creation_date", sa.DateTime(), nullable=False, default=datetime.utcnow),
    sa.Column(
        "last_change_date", sa.DateTime(), nullable=False, default=datetime.utcnow
    ),
    sa.Column("workbench", sa.JSON, nullable=False),
    sa.Column("published", sa.Boolean, nullable=False, default=False),
)
