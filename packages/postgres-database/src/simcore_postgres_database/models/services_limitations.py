""" Groups table

    - List of groups in the framework
    - Groups have a ID, name and a list of users that belong to the group
"""


from typing import Final

import sqlalchemy as sa
from sqlalchemy import event

from ._common import column_created_datetime, column_modified_datetime
from .base import metadata

_TABLE_NAME = "services_limitations"

services_limitations = sa.Table(
    _TABLE_NAME,
    metadata,
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            onupdate="CASCADE",
            ondelete="CASCADE",
            name=f"fk_{_TABLE_NAME}_to_groups_gid",
        ),
        nullable=False,
        doc="Group unique ID",
    ),
    sa.Column(
        "cluster_id",
        sa.BigInteger(),
        sa.ForeignKey(
            "clusters.id",
            name=f"fk_{_TABLE_NAME}_to_clusters_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        nullable=True,
        doc="The cluster id with which these limitations are associated, if NULL or 0 uses the default",
    ),
    sa.Column(
        "ram",
        sa.BigInteger,
        nullable=True,
        doc="defines this group maximum allowable RAM used per service "
        "(None means use defaults, <0 means no limits)",
    ),
    sa.Column(
        "cpu",
        sa.Numeric,
        nullable=True,
        doc="defines this group maximum allowable CPUs used per service "
        "(None means use defaults, <0 means no limits)",
    ),
    sa.Column(
        "vram",
        sa.BigInteger,
        nullable=True,
        doc="defines this group maximum allowable VRAM used per service "
        "(None means use defaults, <0 means no limits)",
    ),
    sa.Column(
        "gpu",
        sa.Numeric,
        nullable=True,
        doc="defines this group maximum allowable CPUs used per service "
        "(None means use defaults, <0 means no limits)",
    ),
    # TIME STAMPS ----
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.UniqueConstraint(
        "gid",
        "cluster_id",
        name="gid_cluster_id_uniqueness",
    ),
    # prevents having multiple entries with NULL cluster (postgres < 15 treats NULL as always different)
    sa.Index(
        "idx_unique_gid_cluster_id_null",
        "gid",
        unique=True,
        postgresql_where=sa.text("cluster_id IS NULL"),
    ),
)


# TRIGGERS ------------------------
TRIGGER_NAME: Final[str] = "trigger_auto_update"  # NOTE: scoped on table
PROCEDURE_NAME: Final[
    str
] = f"{_TABLE_NAME}_auto_update_modified()"  # NOTE: scoped on database
modified_timestamp_trigger = sa.DDL(
    f"""
DROP TRIGGER IF EXISTS {TRIGGER_NAME} on {_TABLE_NAME};
CREATE TRIGGER {TRIGGER_NAME}
BEFORE INSERT OR UPDATE ON {_TABLE_NAME}
FOR EACH ROW EXECUTE PROCEDURE {PROCEDURE_NAME};
    """
)

# PROCEDURES ------------------------
update_modified_timestamp_procedure = sa.DDL(
    f"""
CREATE OR REPLACE FUNCTION {PROCEDURE_NAME}
RETURNS TRIGGER AS $$
BEGIN
  NEW.modified := current_timestamp;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
    """
)

# REGISTER THEM PROCEDURES/TRIGGERS
event.listen(services_limitations, "after_create", update_modified_timestamp_procedure)
event.listen(services_limitations, "after_create", modified_timestamp_trigger)
