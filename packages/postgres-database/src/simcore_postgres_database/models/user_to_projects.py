import sqlalchemy as sa

from .base import metadata
from .projects import projects
from .users import users

user_to_projects = sa.Table(
    "user_to_projects",
    metadata,
    sa.Column("id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("user_id", sa.BigInteger, sa.ForeignKey(users.c.id), nullable=False),
    sa.Column(
        "project_id", sa.BigInteger, sa.ForeignKey(projects.c.id), nullable=False
    ),
)
