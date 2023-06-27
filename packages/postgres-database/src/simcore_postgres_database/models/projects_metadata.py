"""
    These tables were designed to be controled by projects-plugin in
    the webserver's service
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata
from .projects import projects

projects_metadata = sa.Table(
    "projects_metadata",
    #
    # Holds runtime metadata on a project.
    #
    # Things like 'stars', 'quality', 'classifiers' etc (or any kind of stats)
    # should be moved here.
    #
    metadata,
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            projects.c.uuid,
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_projects_metadata_project_uuid",
        ),
        nullable=False,
        primary_key=True,
        doc="The project unique identifier is also used to identify the associated job",
    ),
    sa.Column(
        "user_metadata",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Free json for user to store her metadata",
    ),
    # TIME STAMPS ----
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.PrimaryKeyConstraint("project_uuid"),
)


register_modified_datetime_auto_update_trigger(projects_metadata)


projects_jobs_metadata = sa.Table(
    "projects_jobs_metadata",
    #
    # Every job is mapped to a project and has an ancestor (see job_parent_name)
    # but not every project is associated to a job.
    #
    # This table
    #   - holds all projects associated to jobs
    #   - stores jobs ancestry relations and metadata
    #
    metadata,
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            projects.c.uuid,
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_projects_jobs_metadata_project_uuid",
        ),
        nullable=False,
        primary_key=True,
        doc="The project unique identifier is also used to identify the associated job",
    ),
    sa.Column(
        "parent_name",
        sa.String,
        nullable=False,
        doc="Project's ancestor when create as a job. A project can be created as a"
        " - solver job: solver name (e.g. /v0/solvers/{id}/releases/{version})"
        " - study job: study name (e.g. /v0/studies/{id})",
    ),
    sa.Column(
        "job_metadata",
        JSONB,
        nullable=True,
        server_default=sa.text("'{}'::jsonb"),
        doc="Job can store here metadata. "
        "Preserves class information during serialization/deserialization",
    ),
    # TIME STAMPS ----
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.PrimaryKeyConstraint("project_uuid"),
)

register_modified_datetime_auto_update_trigger(projects_jobs_metadata)
