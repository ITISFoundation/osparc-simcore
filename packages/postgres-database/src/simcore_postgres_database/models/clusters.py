from enum import Enum

import sqlalchemy as sa
from sqlalchemy.sql import func

from .base import metadata

# FIXME: Needs some endpoint/credentials to access the cluster


class ClusterType(Enum):
    AWS = "AWS"
    ON_PREMISE = "ON_PREMISE"


clusters = sa.Table(
    "clusters",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger,
        nullable=False,
        primary_key=True,
        doc="Clusters index",
    ),
    sa.Column("name", sa.String, nullable=False, doc="Display name"),
    sa.Column("description", sa.String, nullable=True, doc="Short description"),
    sa.Column(
        "type",
        sa.Enum(ClusterType),
        nullable=False,
        doc="Classification of the cluster",
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
        nullable=False,
        doc="Identifier of the group that owns this cluster",
    ),
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp auto-generated upon creation",
    ),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),  # this will auto-update on modification
        doc="Timestamp with last update",
    ),
)
