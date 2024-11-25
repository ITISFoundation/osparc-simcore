import sqlalchemy as sa
from sqlalchemy.sql import expression

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata
from .workspaces import workspaces

folders_v2 = sa.Table(
    "folders_v2",
    metadata,
    sa.Column(
        "folder_id",
        sa.BigInteger,
        nullable=False,
        autoincrement=True,
        primary_key=True,
    ),
    sa.Column(
        "name",
        sa.String,
        nullable=False,
        doc="name of the folder",
    ),
    sa.Column(
        "parent_folder_id",
        sa.BigInteger,
        sa.ForeignKey(
            "folders_v2.folder_id",
            name="fk_new_folders_to_folders_id",
        ),
        nullable=True,
    ),
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            "products.name",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_new_folders_to_products_name",
        ),
        nullable=False,
    ),
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey(
            "users.id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_folders_to_user_id",
        ),
        nullable=True,
    ),
    sa.Column(
        "workspace_id",
        sa.BigInteger,
        sa.ForeignKey(
            workspaces.c.workspace_id,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_folders_to_workspace_id",
        ),
        nullable=True,
    ),
    sa.Column(
        "created_by_gid",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_new_folders_to_groups_gid",
            ondelete=RefActions.SET_NULL,
        ),
        nullable=True,
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.Column(
        "trashed_at",
        sa.DateTime(timezone=True),
        nullable=True,
        comment="The date and time when the folder was marked as trashed."
        "Null if the folder has not been trashed [default].",
    ),
    sa.Column(
        "trashed_explicitly",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        comment="Indicates whether the folder was explicitly trashed by the user (true)"
        " or inherited its trashed status from a parent (false) [default].",
    ),
)
