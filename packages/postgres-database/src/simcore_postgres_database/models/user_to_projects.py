import sqlalchemy as sa

from .base import metadata
from .projects import projects
from .users import users

user_to_projects = sa.Table(
    "user_to_projects",
    metadata,
    sa.Column("id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey(users.c.id),  # TODO: , ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "project_id", sa.BigInteger, sa.ForeignKey(projects.c.id), nullable=False,
    ),
    # TODO: do not ondelete=cascase for project_id or it will delete SHARED PROJECT
    # add instead sa.UniqueConstraint('user_id', 'project_id', name='user_project_uniqueness'),
    #
)
