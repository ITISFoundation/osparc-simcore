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
        # FIXME: for some reason, this does not work!? help!
        # sa.ForeignKey(
        #     "services_meta_data.key",
        #     name="fk_services_environments_service_key",
        #     onupdate="CASCADE",
        #     ondelete="CASCADE",
        # ),
        nullable=False,
        doc="Identifies the services that can have access to these environments",
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
        server_default=sa.text(f"{_EVERYONE_GROUP_ID}"),
        doc="Sets to which group these environment applies."
        "Note that a product is also associated to a group",
    ),
    sa.Column(
        "osparc_environments",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="OSPARC_ENVIRONMENT_* identifiers and associated values provided at runtime to the associated service and group",
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
