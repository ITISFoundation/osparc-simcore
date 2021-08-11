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
        "child_index",
        sa.Integer,
        nullable=False,
        unique=True,
        doc="0-based index in order of creation (i.e. 0 being the oldest and N-1 the latest)"
        "from the same parent_id",
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
)


# Snapshot : convert_to_pydantic(snapshot)
