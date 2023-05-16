from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import column_created_datetime, column_modified_datetime
from .base import metadata

# alias
OsparcEnvironmentsDict = dict[str, Any]

#
#  Service vendor environments
#      a vendor can associate identifiers (e.g. a license code) to one of its services
#

services_vendor_environments = sa.Table(
    "services_vendor_environments",
    metadata,
    sa.Column(
        "service_key",
        sa.String,
        doc="A single environment is allowed per service",
    ),
    sa.Column(
        "identifiers_map",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Maps OSPARC_ENVIRONMENT_* identifiers to a value that can be replaced at runtime in compose specs",
    ),
    # TIME STAMPS ----
    column_created_datetime(),
    column_modified_datetime(),
    #
    # CONSTRAINTS --
    #
    sa.PrimaryKeyConstraint(
        "service_key", name="services_vendor_environments_service_key_pk"
    ),
)
