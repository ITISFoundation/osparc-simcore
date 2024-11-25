""" Services table

    - List of 3rd party services in the framework
    - Services have a key, version, and access rights defined by group ids
"""


import sqlalchemy as sa
import typing_extensions
from sqlalchemy.dialects.postgresql import JSONB
from typing_extensions import NotRequired, Required

from ._common import (
    RefActions,
    column_created_datetime,
    column_modified_by_user,
    column_modified_datetime,
)
from .base import metadata
from .users import users


class CompatiblePolicyDict(typing_extensions.TypedDict, total=False):
    # SpecifierSet e.g. ~=0.9
    # SEE https://packaging.python.org/en/latest/specifications/version-specifiers/#id5
    versions_specifier: Required[str]
    # Only necessary if key!=PolicySpecifierDict.key
    other_service_key: NotRequired[str | None]


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
        "custom_policy",
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
        onupdate=RefActions.CASCADE,
        ondelete=RefActions.CASCADE,
    ),
    sa.PrimaryKeyConstraint("key", "version", name="services_compatibility_pk"),
)
