import sqlalchemy as sa

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
        doc="Timestamp for this snapshot."
        "It corresponds to the last_change_date of the parent project "
        "at the time the snapshot was taken.",
    ),
    sa.Column(
        "parent_uuid",
        sa.String,
        sa.ForeignKey(
            "projects.uuid",
            name="fk_snapshots_parent_uuid_projects",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=False,
        doc="UUID of the parent project",
    ),
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            "projects.uuid",
            name="fk_snapshots_project_uuid_projects",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        doc="UUID of the project associated to this snapshot",
    ),
    sa.UniqueConstraint(
        "parent_uuid", "created_at", name="snapshot_from_project_uniqueness"
    ),
)


# Snapshot : convert_to_pydantic(snapshot)
