"""
    Defines specific services/group ID maximal specifications

    A group X may have specific maximal specifications defined when running a jupyter-lab-math
    for example that should run on a specific machine with a specific GPU.

"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from .base import metadata

services_max_specifications = sa.Table(
    "services_max_specifications",
    metadata,
    sa.Column(
        "service_key",
        sa.String,
        nullable=False,
        doc="Service Key Identifier",
    ),
    sa.Column("service_version", sa.String, nullable=False, doc="Service version"),
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_services_max_specifications_gid_groups",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        doc="Group Identifier",
    ),
    sa.Column(
        "sidecar",
        JSONB,
        nullable=True,
        doc="schedule-time specifications for the service sidecar (follows Docker Service creation API, see https://docs.docker.com/engine/api/v1.25/#operation/ServiceCreate)",
    ),
    sa.Column(
        "service",
        JSONB,
        nullable=True,
        doc="schedule-time specifications for the service (follows Docker Service creation API, see https://docs.docker.com/engine/api/v1.41/#tag/Service/operation/ServiceCreate",
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
    # If service-key/version gets deleted from service_metadata, it should be deleted from here
    sa.ForeignKeyConstraint(
        ["service_key", "service_version"],
        ["services_meta_data.key", "services_meta_data.version"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    ),
    sa.PrimaryKeyConstraint(
        "service_key",
        "service_version",
        "gid",
        name="services_max_specifications_pk",
    ),
)

# ------------------------ TRIGGERS
refresh_modified_trigger = sa.text(
    """
DROP TRIGGER IF EXISTS services_max_specifications_modification on services_max_specifications;
CREATE TRIGGER services_max_specifications_modification
BEFORE UPDATE ON services_max_specifications
    FOR EACH ROW
    EXECUTE PROCEDURE refresh_services_max_specifications_modified();
"""
)


# --------------------------- PROCEDURES
refresh_modified_procedure = sa.text(
    """
CREATE OR REPLACE FUNCTION refresh_services_max_specifications_modified() RETURNS TRIGGER AS $$
DECLARE
    group_id BIGINT;
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END; $$ LANGUAGE 'plpgsql';
    """
)

sa.event.listen(services_max_specifications, "after_create", refresh_modified_procedure)
sa.event.listen(
    services_max_specifications,
    "after_create",
    refresh_modified_trigger,
)
