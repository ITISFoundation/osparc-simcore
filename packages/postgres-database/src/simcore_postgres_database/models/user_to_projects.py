import sqlalchemy as sa

from ._common import RefActions
from .base import metadata
from .projects import projects
from .users import users

# DEPRECATED!!!!!!!!!!!!!! DO NOT USE!!!!!!!
user_to_projects = sa.Table(
    "user_to_projects",
    metadata,
    sa.Column("id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey(
            users.c.id,
            name="fk_user_to_projects_id_users",
            ondelete=RefActions.CASCADE,
            onupdate=RefActions.CASCADE,
        ),
        nullable=False,
    ),
    sa.Column(
        "project_id",
        sa.BigInteger,
        sa.ForeignKey(
            projects.c.id,
            name="fk_user_to_projects_id_projects",
            ondelete=RefActions.CASCADE,
            onupdate=RefActions.CASCADE,
        ),
        nullable=False,
    ),
    # TODO: do not ondelete=cascase for project_id or it will delete SHARED PROJECT
    # add instead sa.UniqueConstraint('user_id', 'project_id', name='user_project_uniqueness'),
    #
)
