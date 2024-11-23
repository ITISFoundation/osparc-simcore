from typing import Final

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata

# Intentionally includes the term "SECRET" to avoid leaking this value on a public domain
VENDOR_SECRET_PREFIX: Final[str] = "OSPARC_VARIABLE_VENDOR_SECRET_"


services_vendor_secrets = sa.Table(
    "services_vendor_secrets",
    #
    # - A secret is an environment value passed to the service at runtime
    # - A vendor can associate secrets (e.g. a license code) to any of the services it owns
    # - secrets_map
    #   - keys should be prefixed with OSPARC_VARIABLE_VENDOR_SECRET_ (can still normalize on read)
    #   - values might be encrypted
    #
    metadata,
    sa.Column(
        "service_key",
        sa.String,
        doc="A single environment is allowed per service",
    ),
    sa.Column(
        "service_base_version",
        sa.String,
        doc="Defines the minimum version (included) from which these secrets apply",
    ),
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            "products.name",
            name="fk_services_name_products",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        # NOTE: since this is part of the primary key this is required
        # NOTE: an alternative would be to not use this as a primary key
        server_default="osparc",
        doc="Product Identifier",
    ),
    sa.Column(
        "secrets_map",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Maps OSPARC_VARIABLE_VENDOR_SECRET_* identifiers to a secret value (could be encrypted) "
        "that can be replaced at runtime if found in the compose-specs",
    ),
    # TIME STAMPS ----
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    # CONSTRAINTS --
    sa.ForeignKeyConstraint(
        ["service_key", "service_base_version"],
        ["services_meta_data.key", "services_meta_data.version"],
        onupdate=RefActions.CASCADE,
        ondelete=RefActions.CASCADE,
        # NOTE: this might be a problem: if a version in the metadata is deleted,
        # all versions above will take the secret_map for the previous one.
    ),
    sa.PrimaryKeyConstraint(
        "service_key",
        "service_base_version",
        "product_name",
        name="services_vendor_secrets_pk",
    ),
)
