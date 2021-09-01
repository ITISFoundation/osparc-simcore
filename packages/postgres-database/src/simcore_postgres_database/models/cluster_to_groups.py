import sqlalchemy as sa
from sqlalchemy.sql import expression, func

from .base import metadata

cluster_to_groups = sa.Table(
    "cluster_to_groups",
    metadata,
    sa.Column(
        "cluster_id",
        sa.BigInteger,
        sa.ForeignKey(
            "clusters.id",
            name="fk_cluster_to_groups_id_clusters",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        doc="Cluster unique ID",
    ),
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_cluster_to_groups_gid_groups",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        doc="Group unique IDentifier",
    ),
    # Access Rights flags ---
    sa.Column(
        "read",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        doc="If true, group can use the cluster",
    ),
    sa.Column(
        "write",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        doc="If true, group can modify the cluster",
    ),
    sa.Column(
        "delete",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        doc="If true, group can delete the cluster",
    ),
    # -----
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
        onupdate=func.now(),
        doc="Timestamp with last row update",
    ),
    sa.UniqueConstraint("cluster_id", "gid"),
)
