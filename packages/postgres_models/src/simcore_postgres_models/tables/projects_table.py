"""
    Object Relational Models and access to DB
"""
import enum
import logging
from datetime import datetime

import sqlalchemy as sa

from .base import metadata
from .users_table import users

log = logging.getLogger(__name__)

# ENUM TYPES ----------------------------------------------------------------

class ProjectType(enum.Enum):
    """
        template: template project
        standard: standard project
    """
    TEMPLATE = "template"
    STANDARD = "standard"


# TABLES ----------------------------------------------------------------
#
#  We use a classical Mapping w/o using a Declarative system.
#
# See https://docs.sqlalchemy.org/en/latest/orm/mapping_styles.html#classical-mappings

projects = sa.Table("projects", metadata,
    sa.Column("id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("type", sa.Enum(ProjectType), nullable=False, default=ProjectType.STANDARD),

    sa.Column("uuid", sa.String, nullable=False, unique=True),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("description", sa.String, nullable=False),
    sa.Column("thumbnail", sa.String, nullable=False),
    sa.Column("prj_owner", sa.String, nullable=False),
    sa.Column("creation_date", sa.DateTime(), nullable=False, default=datetime.utcnow),
    sa.Column("last_change_date", sa.DateTime(), nullable=False, default=datetime.utcnow),
    sa.Column("workbench", sa.JSON, nullable=False)
)

user_to_projects = sa.Table("user_to_projects", metadata,
    sa.Column("id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("user_id", sa.BigInteger, sa.ForeignKey(users.c.id), nullable=False),
    sa.Column("project_id", sa.BigInteger, sa.ForeignKey(projects.c.id), nullable=False)
)
