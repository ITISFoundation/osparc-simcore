"""Users pre-registration details table

- Stores details of users during the pre-registration phase.

Migration strategy:
- The primary key is `id`, which is unique and sufficient for migration.
- Ensure foreign key references to `users` are valid in the target database.
- No additional changes are required; this table can be migrated as is.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from .base import metadata
from .users import users

users_pre_registration_details = sa.Table(
    "users_pre_registration_details",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger,
        nullable=False,
        primary_key=True,
        autoincrement=True,
        doc="Unique identifier for the pre-registration detail",
    ),
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey(
            users.c.id,
            name="fk_users_pre_registration_details_user_id",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
        doc="Reference to the user associated with this pre-registration detail",
    ),
    sa.Column(
        "details",
        JSONB,
        nullable=False,
        doc="JSONB column to store pre-registration details",
    ),
    sa.Column(
        "created_at",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when the pre-registration detail was created",
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp when the pre-registration detail was last updated",
    ),
)
