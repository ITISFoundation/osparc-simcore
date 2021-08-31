import sqlalchemy as sa

from .base import metadata

#
# Identifies which projects are versioned
#
projects_repos = sa.Table(
    "projects_repos",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger,
        nullable=False,
        primary_key=True,
        doc="Global repo identifier index",
    ),
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            "projects.uuid",
            name="fk_projects_repos_project_uuid",
            onupdate="CASCADE",
            # ondelete: if project is deleted, this repo is invalidated.
        ),
        nullable=False,
        unique=True,
        doc="Project under version control"
        "Used as a working copy (WC) to produce/checkout snapshots.",
    ),
    sa.Column(
        "staging_id",
        sa.BigInteger,
        sa.ForeignKey(
            "projects_checkpoints.id",
            name="fk_projects_repos_staging_id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=True,
        doc="Points to the staging entrypoint",
    ),
    sa.Column(
        "head_id",
        sa.BigInteger,
        sa.ForeignKey(
            "projects_checkpoints.id",
            name="fk_projects_repos_head_id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=True,
        doc="Current commit this repository is viewing"
        "First checkout will replace the working copy with this snapshot",
    ),
)

#
# An checkpoint is combination of a git commit and a tag at the same time
# It identifies a snapshot (snapshot_uuid) taken of a project at a given time
#
projects_checkpoints = sa.Table(
    "projects_checkpoints",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger,
        nullable=False,
        primary_key=True,
        doc="Global identifier throughout all repository's checkpoints",
    ),
    sa.Column(
        "repo_id",
        sa.BigInteger,
        nullable=False,
        doc="Repository to which this checkpoint belongs",
    ),
    sa.Column(
        "parent",
        sa.BigInteger,
        sa.ForeignKey(
            "projects_checkpoints.id",
            name="fk_checkpoints_parent__checkpoints",
            onupdate="CASCADE",
        ),
        nullable=True,
        doc="Preceding checkpoint",
    ),
    sa.Column("tag", sa.String, doc="Display name"),
    sa.Column("message", sa.String, doc="Commit message"),
    sa.Column(
        "snapshot_checksum",
        sa.String,
        nullable=False,
        doc="SHA-1 checksum of snapshot."
        "Used as revision/commit identifier since it is unique per repo",
    ),
    sa.Column(
        "snapshot_uuid",
        sa.String,
        sa.ForeignKey(
            "projects.uuid",
            name="fk_checkpoints_project_uuid_projects",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
        unique=True,
        doc="UUID of the project snapshot associated to this checkpoint",
    ),
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,
        doc="Timestamp for this snapshot."
        "It corresponds to the last_change_date of the parent project "
        "at the time the snapshot was taken.",
    ),
    # CONSTRAINTS --------------
    sa.UniqueConstraint("tag", "repo_id", name="repo_tag_uniqueness"),
)
