from typing import Final

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import column_created_datetime, column_modified_datetime
from .base import metadata

# Intentionally includes the term "SECRET" to avoid leaking this value on a public domain
VENDOR_SECRET_PREFIX: Final[str] = "OSPARC_VENDOR_SECRET_"


services_vendor_secrets = sa.Table(
    "services_vendor_secrets",
    #
    # - A secret is an environment value passed to the service at runtime
    # - A vendor can associate secrets (e.g. a license code) to any of the services it owns
    # - secrets_map
    #   - keys should be prefixed with OSPARC_VENDOR_SECRET_ (can still normalize on read)
    #   - values might be encrypted
    #
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
        doc="Maps OSPARC_VENDOR_SECRET_* identifiers to a secret value (could be encrypted) "
        "that can be replaced at runtime if found in the compose-specs",
    ),
    # TIME STAMPS ----
    column_created_datetime(),
    column_modified_datetime(),
    # CONSTRAINTS --
    sa.PrimaryKeyConstraint(
        "service_key", name="services_vendor_secrets_service_key_pk"
    ),
)
