import sqlalchemy as sa
from sqlalchemy.sql import expression

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata
from .groups import groups
from .projects import projects

project_to_groups = sa.Table(
    "project_to_groups",
    metadata,
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            projects.c.uuid,
            name="fk_project_to_groups_project_uuid",
            ondelete=RefActions.CASCADE,
            onupdate=RefActions.CASCADE,
        ),
        index=True,
        nullable=False,
        doc="project reference for this table",
    ),
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey(
            groups.c.gid,
            name="fk_project_to_groups_gid_groups",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Group unique IDentifier",
    ),
    # Access Rights flags ---
    sa.Column(
        "read",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        doc="If true, group can open the project",
    ),
    sa.Column(
        "write",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        doc="If true, group can modify the project",
    ),
    sa.Column(
        "delete",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        doc="If true, group can delete the project",
    ),
    # -----
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.UniqueConstraint("project_uuid", "gid"),
)
