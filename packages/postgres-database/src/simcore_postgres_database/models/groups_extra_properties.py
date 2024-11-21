import sqlalchemy as sa

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata

groups_extra_properties = sa.Table(
    "groups_extra_properties",
    # groups_extra_properties: Maps internet access permissions to groups
    metadata,
    sa.Column(
        "group_id",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_groups_extra_properties_to_group_group_id",
        ),
        nullable=False,
        doc="Group unique ID",
    ),
    sa.Column(
        "product_name",
        sa.VARCHAR,
        sa.ForeignKey(
            "products.name",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_groups_extra_properties_to_products_name",
        ),
        nullable=False,
        doc="Product unique identifier",
    ),
    sa.Column(
        "internet_access",
        sa.Boolean(),
        nullable=False,
        server_default=sa.sql.expression.true(),
        doc="If true, group has internet access. "
        "If a user is part of this group, it's "
        "service can access the internet.",
    ),
    sa.Column(
        "override_services_specifications",
        sa.Boolean(),
        nullable=False,
        server_default=sa.sql.expression.false(),
        doc="allows group to override default service specifications.",
    ),
    sa.Column(
        "use_on_demand_clusters",
        sa.Boolean(),
        nullable=False,
        server_default=sa.sql.expression.false(),
        doc="If true, group will use on-demand clusters",
    ),
    sa.Column(
        "enable_telemetry",
        sa.Boolean(),
        nullable=False,
        server_default=sa.sql.expression.false(),
        doc="If true, will send telemetry for new style dynamic services to frontend",
    ),
    sa.Column(
        "enable_efs",
        sa.Boolean(),
        nullable=False,
        server_default=sa.sql.expression.false(),
        doc="If true, will mount efs distributed file system when dynamic services starts",
    ),
    sa.UniqueConstraint(
        "group_id", "product_name", name="group_id_product_name_uniqueness"
    ),
    # TIME STAMPS ----
    column_created_datetime(timezone=False),
    column_modified_datetime(timezone=False),
)
