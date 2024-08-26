import sqlalchemy as sa

from .base import metadata
from .projects import projects
from .tags import tags

projects_tags = sa.Table(
    #
    # Tags associated to a project (many-to-many relation)
    #
    "projects_tags",
    metadata,
    sa.Column(
        "project_id",
        sa.BigInteger,
        sa.ForeignKey(projects.c.id, onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        doc="NOTE that project.c.id != project.c.uuid",
    ),
    sa.Column(
        "tag_id",
        sa.BigInteger,
        sa.ForeignKey(tags.c.id, onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.UniqueConstraint("project_id", "tag_id"),
)
