import sqlalchemy as sa

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata

folders = sa.Table(
    "folders",
    metadata,
    sa.Column(
        "id",
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
        "description",
        sa.String,
        nullable=False,
        server_default="",
        doc="user provided description for the folder",
    ),
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            "products.name",
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_folders_to_products_name",
        ),
        nullable=False,
        doc="product identifier",
    ),
    sa.Column(
        "created_by",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_folders_to_groups_gid",
            ondelete="SET NULL",
        ),
        nullable=True,
        doc="traces who created the folder",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
)


register_modified_datetime_auto_update_trigger(folders)

folders_access_rights = sa.Table(
    "folders_access_rights",
    metadata,
    sa.Column(
        "folder_id",
        sa.BigInteger,
        sa.ForeignKey(
            "folders.id",
            name="fk_folders_access_rights_to_folders_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_folders_access_rights_to_groups_gid",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    sa.Column(
        "traversal_parent_id",
        sa.BigInteger,
        sa.ForeignKey(
            "folders.id",
            name="fk_folders_to_folders_id_via_traversal_parent_id",
            ondelete="SET NULL",
        ),
        doc=(
            "used for listing the contes of the folders, "
            "can be changed by the user by moving the folder"
        ),
    ),
    sa.Column(
        "original_parent_id",
        sa.BigInteger,
        sa.ForeignKey(
            "folders.id",
            name="fk_folders_to_folders_id_via_original_parent_id",
            ondelete="SET NULL",
        ),
        doc=(
            "initially equal the same as `traversal_parent_id`, "
            "keeps track of the original parent, "
            "can never be changed once insteted"
        ),
    ),
    sa.Column(
        "read",
        sa.Boolean(),
        nullable=False,
        doc=(
            "if True can: "
            "view folders inside current folder "
            "view projects inside current folder"
        ),
    ),
    sa.Column(
        "write",
        sa.Boolean(),
        nullable=False,
        doc=(
            "if True can: "
            "create folder inside current folder, "
            "add project to folder"
        ),
    ),
    sa.Column(
        "delete",
        sa.Boolean(),
        nullable=False,
        doc=(
            "if True can: "
            "share folder, "
            "rename folder, "
            "edit folder description, "
            "delete folder, "
            "delete project form folder"
        ),
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.PrimaryKeyConstraint("folder_id", "gid", name="folders_access_rights_pk"),
)

register_modified_datetime_auto_update_trigger(folders_access_rights)


folders_to_projects = sa.Table(
    "folders_to_projects",
    metadata,
    sa.Column(
        "folder_id",
        sa.BigInteger,
        sa.ForeignKey(
            "folders.id",
            name="fk_folders_to_projects_to_folders_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            "projects.uuid",
            name="fk_folders_to_projects_to_projects_uuid",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.PrimaryKeyConstraint("folder_id", "project_uuid", name="projects_to_folder_pk"),
)

register_modified_datetime_auto_update_trigger(folders_to_projects)
