"""
    Defines specific services/group ID specifications

    A group X may have special specifications defined when running a jupyter-lab-math
    for example that should run on a specific machine.

"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import RefActions
from .base import metadata

services_specifications = sa.Table(
    "services_specifications",
    metadata,
    sa.Column(
        "service_key",
        sa.String,
        nullable=False,
        doc="Service Key Identifier",
    ),
    sa.Column(
        "service_version",
        sa.String,
        nullable=False,
        doc="Service version",
    ),
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_services_specifications_gid_groups",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
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
    # If service-key/version gets deleted from service_metadata, it should be deleted from here
    sa.ForeignKeyConstraint(
        ["service_key", "service_version"],
        ["services_meta_data.key", "services_meta_data.version"],
        onupdate=RefActions.CASCADE,
        ondelete=RefActions.CASCADE,
    ),
    # This table stores services (key:version) that consume filetype by AT LEAST one input_port
    # if more ports can consume, then it should only be added once in this table
    sa.PrimaryKeyConstraint(
        "service_key",
        "service_version",
        "gid",
        name="services_specifications_pk",
    ),
)
