""" Services table

    - List of 3rd party services in the framework
    - Services have a key, version, and access rights defined by group ids
"""

from typing import TypedDict

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import (
    column_created_datetime,
    column_modified_by_user,
    column_modified_datetime,
)
from .base import metadata
from .users import users


class PolicySpecifierDict(TypedDict, total=False):
    version: str  # SpecifierSet e.g. ~=0.9, SEE https://packaging.python.org/en/latest/specifications/version-specifiers/#id5
    key: str | None  # Only necessary if key!=PolicySpecifierDict.key


services_compatibility = sa.Table(
    #
    # CUSTOM COMPATIBILITY POLICIES
    # Otherwise default compatibility policy is employed.
    #
    "services_compatibility",
    metadata,
    sa.Column(
        "key",
        sa.String,
        nullable=False,
        doc="Service Key Identifier",
    ),
    sa.Column(
        "version",
        sa.String,
        nullable=False,
        doc="Service version",
    ),
    sa.Column(
        "policy_specifier",
        JSONB,
        nullable=False,
        doc="PolicySpecifierDict with custom policy",
    ),
    # Traceability, i.e. when
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    # Traceability, i.e. who
    column_modified_by_user(users_table=users, required=True),
    # Constraints
    sa.ForeignKeyConstraint(
        ["key", "version"],
        ["services_meta_data.key", "services_meta_data.version"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    ),
    sa.PrimaryKeyConstraint("key", "version", name="services_compatibility_pk"),
)
