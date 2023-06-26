"""
    These tables were designed to be controled by projects-plugin in
    the webserver's service
"""

import sqlalchemy as sa

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata
from .projects import projects

projects_to_jobs = sa.Table(
    "projects_to_jobs",
    #
    # Every job is mapped to a project and has an ancestor (see job_parent_name)
    # but not every project is associated to a job.
    #
    # This table holds all projects associated to jobs
    #
    metadata,
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            projects.c.uuid,
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_projects_to_jobs_project_uuid",
        ),
        nullable=False,
        primary_key=True,
        doc="The project unique identifier is also used to identify the associated job",
    ),
    sa.Column(
        "job_parent_name",
        sa.String,
        nullable=False,
        doc="Project's ancestor when create as a job. A project can be created as a"
        " - solver job: solver name (e.g. /v0/solvers/{id}/releases/{version})"
        " - study job: study name (e.g. /v0/studies/{id})",
    ),
    # TIME STAMPS ----
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.PrimaryKeyConstraint("project_uuid"),
)

register_modified_datetime_auto_update_trigger(projects_to_jobs)
