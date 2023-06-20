import sqlalchemy as sa

from ._common import column_created_datetime, column_modified_datetime
from .base import metadata
from .projects import projects

projects_comments = sa.Table(
    "projects_comments",
    metadata,
    sa.Column(
        "comment_id",
        sa.BigInteger,
        nullable=False,
        autoincrement=True,
        primary_key=True,
        doc="Primary key, identifies the comment",
    ),
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            projects.c.uuid,
            name="fk_projects_comments_project_uuid",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        index=True,
        doc="project reference for this table",
    ),
    sa.Column(
        "user_id",
        sa.BigInteger,
        doc="user reference for this table",
    ),
    sa.Column(
        "contents",
        sa.String,
        nullable=False,
        doc="Content of the comment",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.PrimaryKeyConstraint("comment_id", name="projects_comments_pkey"),
)
