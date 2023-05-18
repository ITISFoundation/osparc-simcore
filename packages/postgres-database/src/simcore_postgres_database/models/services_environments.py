from typing import Any, Final, TypeAlias

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import column_created_datetime, column_modified_datetime
from .base import metadata

VendorSecretsDict: TypeAlias = dict[str, Any]

# NOTE: this prefix intentionally stresses that the value is secret to avoid leaking this value
#       on a public domain
VENDOR_SECRET_PREFIX: Final[str] = "OSPARC_VENDOR_SECRET_"


#
#  Service vendor secret environments
#    - a vendor can associate secrets (e.g. a license code) to one of its services
#    - values could be encrypted


services_vendor_secrets = sa.Table(
    "services_vendor_secrets",
    metadata,
    sa.Column(
        "service_key",
        sa.String,
        doc="A single environment is allowed per service",
    ),
    sa.Column(
        "secrets_map",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Maps OSPARC_VENDOR_SECRET_* identifiers to a secret value that can be replaced at runtime in compose specs",
    ),
    # TIME STAMPS ----
    column_created_datetime(),
    column_modified_datetime(),
    #
    # CONSTRAINTS --
    #
    sa.PrimaryKeyConstraint(
        "service_key", name="services_vendor_secrets_service_key_pk"
    ),
)
