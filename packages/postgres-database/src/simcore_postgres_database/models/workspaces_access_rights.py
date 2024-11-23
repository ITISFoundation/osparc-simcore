import sqlalchemy as sa
from sqlalchemy.sql import expression

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata
from .groups import groups
from .workspaces import workspaces

workspaces_access_rights = sa.Table(
    "workspaces_access_rights",
    metadata,
    sa.Column(
        "workspace_id",
        sa.BigInteger,
        sa.ForeignKey(
            workspaces.c.workspace_id,
            name="fk_workspaces_access_rights_id_workspaces",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        doc="Workspace unique ID",
    ),
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey(
            groups.c.gid,
            name="fk_workspaces_access_rights_gid_groups",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        doc="Group unique IDentifier",
    ),
    # Access Rights flags ---
    sa.Column(
        "read",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        doc="If true, group can use the workspace",
    ),
    sa.Column(
        "write",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        doc="If true, group can modify the workspace",
    ),
    sa.Column(
        "delete",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        doc="If true, group can delete the workspace",
    ),
    # -----
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.UniqueConstraint("workspace_id", "gid"),
)
