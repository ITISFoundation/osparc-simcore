import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

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
    sa.Column(
        "access_rights",
        JSONB,
        nullable=False,
        server_default=sa.text(
            '\'{"read": true, "write": false, "delete": false}\'::jsonb'
        ),
        doc="Group's access rights to the cluster",
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
        onupdate=func.now(),
        doc="Timestamp with last row update",
    ),
    sa.UniqueConstraint("cluster_id", "gid"),
)
