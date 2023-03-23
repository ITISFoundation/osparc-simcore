""" Services table

    - List of 3rd party services in the framework
    - Services have a key, version, and access rights defined by group ids
"""

import sqlalchemy as sa
from sqlalchemy import null
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.sql import expression, func

from .base import metadata

services_meta_data = sa.Table(
    "services_meta_data",
    metadata,
    sa.Column(
        "key",
        sa.String,
        nullable=False,
        doc="Hierarchical identifier of the service e.g. simcore/services/dynamic/my-super-service",
    ),
    sa.Column(
        "version",
        sa.String,
        nullable=False,
        doc="MAJOR.MINOR.PATCH semantic versioning (see https://semver.org)",
    ),
    sa.Column(
        "owner",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_services_meta_data_gid_groups",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=True,
        doc="Identifier of the group that owns this service",
    ),
    sa.Column(
        "name",
        sa.String,
        nullable=False,
        doc="Display label",
    ),
    sa.Column(
        "description",
        sa.String,
        nullable=False,
        doc="Markdown-compatible description",
    ),
    sa.Column(
        "thumbnail",
        sa.String,
        nullable=True,
        doc="Link to image to us as service thumbnail",
    ),
    sa.Column(
        "classifiers",
        ARRAY(sa.String, dimensions=1),
        nullable=False,
        server_default="{}",
        doc="List of standard labels that describe this service (see classifiers table)",
    ),
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp on creation",
    ),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp with last update",
    ),
    sa.Column(
        "deprecated",
        sa.DateTime(),
        nullable=True,
        server_default=null(),
        doc="Timestamp with deprecation date",
    ),
    sa.Column(
        "quality",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Free JSON with quality assesment based on TSR",
    ),
    sa.PrimaryKeyConstraint("key", "version", name="services_meta_data_pk"),
)


#
# services_access_rights table:
#   Defines access rights (execute_access, write_access) on a service (key)
#   for a given group (gid) on a product (project_name)
#

services_access_rights = sa.Table(
    "services_access_rights",
    metadata,
    sa.Column(
        "key",
        sa.String,
        nullable=False,
        doc="Service Key Identifier",
    ),
    sa.Column("version", sa.String, nullable=False, doc="Service version"),
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_services_gid_groups",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        doc="Group Identifier",
    ),
    # Access Rights flags ---
    sa.Column(
        "execute_access",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        doc="If true, group can execute the service",
    ),
    sa.Column(
        "write_access",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        doc="If true, group can modify the service",
    ),
    # -----
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            "products.name",
            name="fk_services_name_products",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        doc="Product Identifier",
    ),
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp of creation",
    ),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp on last update",
    ),
    sa.ForeignKeyConstraint(
        ["key", "version"],
        ["services_meta_data.key", "services_meta_data.version"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    ),
    sa.PrimaryKeyConstraint(
        "key", "version", "gid", "product_name", name="services_access_pk"
    ),
)


#
# services_latest table:
#   Keeps latest version of every service (key)
#

services_latest = sa.Table(
    "services_latest",
    metadata,
    sa.Column(
        "key",
        sa.String,
        nullable=False,
        doc="Hierarchical identifier of the service e.g. simcore/services/dynamic/my-super-service",
    ),
    sa.Column(
        "version",
        sa.String,
        nullable=False,
        doc="MAJOR.MINOR.PATCH semantic versioning (see https://semver.org)",
    ),
    sa.ForeignKeyConstraint(
        ["key", "version"],
        ["services_meta_data.key", "services_meta_data.version"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    ),
    sa.PrimaryKeyConstraint("key", name="services_latest_pk"),
)
