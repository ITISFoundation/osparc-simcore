"""Function jobs access rights table"""

import sqlalchemy as sa
from simcore_postgres_database.models._common import (
    RefActions,
    column_created_datetime,
    column_modified_datetime,
)

from .base import metadata
from .funcapi_function_jobs_table import function_jobs_table

function_jobs_access_rights_table = sa.Table(
    "funcapi_function_jobs_access_rights",
    metadata,
    sa.Column(
        "function_job_uuid",
        sa.ForeignKey(
            function_jobs_table.c.uuid,
            name="fk_func_access_to_func_jobs_to_func_job_uuid",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Unique identifier of the function job",
    ),
    sa.Column(
        "user_id",
        sa.ForeignKey(
            "users.id",
            name="fk_func_access_to_users_user_id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        doc="User id",
    ),
    sa.Column(
        "group_id",
        sa.ForeignKey(
            "groups.gid",
            name="fk_func_access_to_groups_group_id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        doc="Group id",
    ),
    sa.Column(
        "read",
        sa.Boolean,
        doc="Read access right for the function job",
    ),
    sa.Column(
        "write",
        sa.Boolean,
        doc="Write access right for the function job",
    ),
    sa.Column(
        "execute",
        sa.Boolean,
        doc="Execute access right for the function job",
    ),
    column_created_datetime(),
    column_modified_datetime(),
    sa.CheckConstraint(
        sa.or_(
            sa.and_(sa.column("user_id").is_(None), sa.column("group_id").isnot(None)),
            sa.and_(sa.column("user_id").isnot(None), sa.column("group_id").is_(None)),
        ),
        name="ck_user_or_group_exclusive",
    ),  # Instead of using two tables, i make sure one of these is None
    sa.PrimaryKeyConstraint(
        "function_job_uuid",
        "user_id",
        "group_id",
        name="funcapi_function_jobs_access_rights_pk",
    ),
)
