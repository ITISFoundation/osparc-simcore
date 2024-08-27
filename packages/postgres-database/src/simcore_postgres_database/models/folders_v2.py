import sqlalchemy as sa

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
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
        doc="Primary key",
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
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_new_folders_to_products_name",
        ),
        nullable=False,
    ),
    sa.Column(
        "user_id",
        sa.String,
        sa.ForeignKey(
            "users.id",
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_folders_to_user_id",
        ),
        nullable=True,
    ),
    sa.Column(
        "workspace_id",
        sa.String,
        sa.ForeignKey(
            workspaces.c.workspace_id,
            onupdate="CASCADE",
            ondelete="CASCADE",
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
            ondelete="SET NULL",
        ),
        nullable=True,
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
)


register_modified_datetime_auto_update_trigger(folders_v2)
