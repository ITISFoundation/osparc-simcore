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
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
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
        nullable=True,
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
        nullable=True,
        doc="Group id",
    ),
    sa.Column(
        "read",
        sa.Boolean,
        default=False,
        doc="Read access right for the function",
    ),
    sa.Column(
        "write",
        sa.Boolean,
        default=False,
        doc="Write access right for the function",
    ),
    sa.Column(
        "execute",
        sa.Boolean,
        default=False,
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
    sa.UniqueConstraint(
        "user_id",
        "group_id",
        name="uq_funcapi_functions_access_rights_user_group",
    ),
)
