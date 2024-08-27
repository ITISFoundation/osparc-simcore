import sqlalchemy as sa

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata
from .folders_v2 import folders_v2

projects_to_folders = sa.Table(
    "projects_to_folders",
    metadata,
    sa.Column(
        "folder_id",
        sa.BigInteger,
        sa.ForeignKey(
            folders_v2.c.folder_id,
            name="fk_projects_to_folders_to_folders_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            "projects.uuid",
            name="fk_projects_to_folders_to_projects_uuid",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
)

register_modified_datetime_auto_update_trigger(projects_to_folders)
