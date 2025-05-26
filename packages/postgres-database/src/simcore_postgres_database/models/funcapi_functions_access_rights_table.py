"""Functions access rights table"""

import sqlalchemy as sa
from simcore_postgres_database.models._common import (
    RefActions,
    column_created_datetime,
    column_modified_datetime,
)

from .base import metadata
from .funcapi_functions_table import functions_table

functions_access_rights_table = sa.Table(
    "funcapi_functions_access_rights",
    metadata,
    sa.Column(
        "function_uuid",
        sa.ForeignKey(
            functions_table.c.uuid,
            name="fk_func_access_to_func_to_func_uuid",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Unique identifier of the function",
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
        doc="Read access right for the function",
    ),
    sa.Column(
        "write",
        sa.Boolean,
        doc="Write access right for the function",
    ),
    sa.Column(
        "execute",
        sa.Boolean,
        doc="Execute access right for the function",
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
        "function_uuid",
        "user_id",
        "group_id",
        name="funcapi_functions_access_rights_pk",
    ),
)
