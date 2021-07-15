import sqlalchemy as sa
from sqlalchemy.sql import func

from .base import metadata

snapshots = sa.Table(
    "snapshots",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger,
        nullable=False,
        primary_key=True,
        doc="Global snapshot identifier index",
    ),
    sa.Column("name", sa.String, nullable=False, doc="Display name"),
    sa.Column(
        "created_at",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp on creation",
    ),
    sa.Column(
        "parent_uuid",
        sa.String,
        nullable=False,
        unique=True,
        doc="UUID of the parent project",
    ),
    sa.Column(
        "project_uuid",
        sa.String,
        nullable=False,
        unique=True,
        doc="UUID of the project associated to this snapshot",
    ),
)
