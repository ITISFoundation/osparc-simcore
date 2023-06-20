import sqlalchemy as sa
from sqlalchemy.sql import func

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
        "content",
        sa.String,
        nullable=True,
        doc="Content of the comment",
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp on creation",
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp with last update",
    ),
    sa.PrimaryKeyConstraint("comment_id", name="projects_comments_pkey"),
)
