import sqlalchemy as sa

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
        "parent_folder",
        sa.BigInteger,
        sa.ForeignKey(
            "folders.id",
            name="fk_folders_to_folders_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
)

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
        "read",
        sa.Boolean(),
        nullable=False,
        doc="read access on folder content",
    ),
    sa.Column(
        "write",
        sa.Boolean(),
        nullable=False,
        doc="write access on folder content",
    ),
    sa.Column(
        "delete",
        sa.Boolean(),
        nullable=False,
        doc="can remove the the entry pointed by folder_id",
    ),
    sa.PrimaryKeyConstraint("folder_id", "gid", name="folders_access_rights_pk"),
)


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
        "project_id",
        sa.BigInteger,
        sa.ForeignKey(
            "projects.id",
            name="fk_folders_to_projects_to_projects_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    sa.PrimaryKeyConstraint("folder_id", "project_id", name="projects_to_folder_pk"),
)
