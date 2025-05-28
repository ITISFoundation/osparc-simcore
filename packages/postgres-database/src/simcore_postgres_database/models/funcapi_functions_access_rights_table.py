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
        "group_id",
        sa.ForeignKey(
            "groups.gid",
            name="fk_func_access_to_groups_group_id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
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
    sa.PrimaryKeyConstraint(
        "function_uuid", "group_id", name="pk_func_access_to_func_group"
    ),
)
