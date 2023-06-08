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
        primary_key=True,
        doc="Group unique ID",
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
