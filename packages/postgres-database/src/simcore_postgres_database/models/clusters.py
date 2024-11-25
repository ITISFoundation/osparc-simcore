from enum import Enum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ._common import RefActions
from .base import metadata


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
            name="fk_clusters_gid_groups",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.RESTRICT,
        ),
        nullable=False,
        doc="Identifier of the group that owns this cluster",
    ),
    sa.Column(
        "thumbnail",
        sa.String,
        nullable=True,
        doc="Link to image as to cluster thumbnail",
    ),
    sa.Column("endpoint", sa.String, nullable=False, doc="URL to access the cluster"),
    sa.Column(
        "authentication",
        JSONB,
        nullable=False,
        doc="Authentication options (can be any of simple password, kerberos or jupyterhub"
        ", for details see https://gateway.dask.org/authentication.html#",
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

# ------------------------ TRIGGERS
new_cluster_trigger = sa.DDL(
    """
DROP TRIGGER IF EXISTS cluster_modification on clusters;
CREATE TRIGGER cluster_modification
AFTER INSERT ON clusters
    FOR EACH ROW
    EXECUTE PROCEDURE set_cluster_to_owner_group();
"""
)


# --------------------------- PROCEDURES
assign_cluster_access_rights_to_owner_group_procedure = sa.DDL(
    """
CREATE OR REPLACE FUNCTION set_cluster_to_owner_group() RETURNS TRIGGER AS $$
DECLARE
    group_id BIGINT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO "cluster_to_groups" ("gid", "cluster_id", "read", "write", "delete") VALUES (NEW.owner, NEW.id, TRUE, TRUE, TRUE);
    END IF;
    RETURN NULL;
END; $$ LANGUAGE 'plpgsql';
    """
)

sa.event.listen(
    clusters, "after_create", assign_cluster_access_rights_to_owner_group_procedure
)
sa.event.listen(
    clusters,
    "after_create",
    new_cluster_trigger,
)
