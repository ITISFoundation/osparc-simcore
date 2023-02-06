import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import column_created_datetime, column_modified_datetime
from .base import metadata

_EVERYONE_GROUP_ID = 1

services_environments = sa.Table(
    "services_environments",
    metadata,
    sa.Column(
        "service_key",
        sa.String,
        nullable=False,
        doc="Service Key Identifier or a glob of it",
    ),
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_services_environments_gid_groups",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        server_default=_EVERYONE_GROUP_ID,
        doc="Sets to which group these environment applies",
    ),
    sa.Column(
        "osparc_environments",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="OSPARC_ENVIRONMENT_* identifiers and associated value",
    ),
    sa.PrimaryKeyConstraint(
        "service_key",
        "gid",
        name="services_environments_pk",
    ),
    # TIME STAMPS ----
    column_created_datetime(),
    column_modified_datetime(),
)
