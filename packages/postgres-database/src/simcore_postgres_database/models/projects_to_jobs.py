import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from ._common import RefActions
from .base import metadata
from .projects import projects

projects_to_jobs = sa.Table(
    "projects_to_jobs",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger,
        primary_key=True,
        autoincrement=True,
        doc="Identifier index",
    ),
    sa.Column(
        "project_uuid",
        UUID(as_uuid=True),
        sa.ForeignKey(
            projects.c.uuid,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_projects_to_jobs_project_uuid",
        ),
        nullable=False,
        doc="Foreign key to projects.uuid",
    ),
    sa.Column(
        "job_name",
        sa.String,
        nullable=False,
        doc="Identifier for the job associated with the project",
    ),
    sa.UniqueConstraint(
        "project_uuid", "job_name", name="uq_projects_to_jobs_project_uuid_job_name"
    ),
    comment="Maps projects.uuid to job_name",
)
