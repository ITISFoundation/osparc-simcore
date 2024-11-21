import sqlalchemy as sa

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata
from .folders_v2 import folders_v2

projects_to_folders = sa.Table(
    "projects_to_folders",
    metadata,
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            "projects.uuid",
            name="fk_projects_to_folders_to_projects_uuid",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
    ),
    sa.Column(
        "folder_id",
        sa.BigInteger,
        sa.ForeignKey(
            folders_v2.c.folder_id,
            name="fk_projects_to_folders_to_folders_id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
    ),
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey(
            "users.id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_projects_to_folders_to_user_id",
        ),
        nullable=True,
        doc="If private workspace then user id is filled, otherwise its null",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.UniqueConstraint("project_uuid", "folder_id", "user_id"),
)
