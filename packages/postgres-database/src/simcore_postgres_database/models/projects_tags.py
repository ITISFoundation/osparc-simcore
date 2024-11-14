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
        sa.ForeignKey(
            projects.c.id,
            onupdate="CASCADE",
            ondelete="SET NULL",
            name="project_tags_project_id_fkey",
        ),
        nullable=True,  # <-- NULL means that project was deleted
        doc="NOTE that project.c.id != project.c.uuid",
    ),
    sa.Column(
        "tag_id",
        sa.BigInteger,
        sa.ForeignKey(tags.c.id, onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "project_uuid",
        sa.String,
        nullable=False,
    ),
    sa.UniqueConstraint(
        "project_uuid", "tag_id", name="project_tags_project_uuid_unique"
    ),
)
