import sqlalchemy as sa

from ._common import RefActions
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
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.SET_NULL,
            name="project_tags_project_id_fkey",
        ),
        nullable=True,  # <-- NULL means that project was deleted
        doc="NOTE that project.c.id != project.c.uuid. If project is deleted, we do not delete project in this table, we just set this column to NULL. Why? Because the `project_uuid_for_rut` is still used by resource usage tracker",
    ),
    sa.Column(
        "tag_id",
        sa.BigInteger,
        sa.ForeignKey(
            tags.c.id, onupdate=RefActions.CASCADE, ondelete=RefActions.CASCADE
        ),
        nullable=False,
    ),
    sa.Column(
        "project_uuid_for_rut",
        sa.String,
        nullable=False,
    ),
    sa.UniqueConstraint(
        "project_uuid_for_rut", "tag_id", name="project_tags_project_uuid_unique"
    ),
)
