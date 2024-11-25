import sqlalchemy as sa

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata
from .projects import projects
from .users import users

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
            ondelete=RefActions.CASCADE,
            onupdate=RefActions.CASCADE,
        ),
        index=True,
        nullable=False,
        doc="project reference for this table",
    ),
    # NOTE: if the user gets deleted, it sets to null which should be interpreted as "unknown" user
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey(
            users.c.id,
            name="fk_projects_comments_user_id",
            ondelete=RefActions.SET_NULL,
        ),
        doc="user who created the comment",
        nullable=True,
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
