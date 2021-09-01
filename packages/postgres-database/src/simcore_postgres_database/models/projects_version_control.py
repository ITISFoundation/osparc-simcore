#
# TODO: create template to produce these tables over another table other than project
#

import sqlalchemy as sa
from sqlalchemy.sql import func

from .base import metadata

# REPOSITORES
#
# Projects under version-control are assigned a repository
#   - keeps HEAD ref to a
#
#
projects_vc_repos = sa.Table(
    "projects_vc_repos",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger,
        nullable=False,
        primary_key=True,
        doc="Global vc repo identifier index",
    ),
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            "projects.uuid",
            name="fk_projects_vc_repos_project_uuid",
            onupdate="CASCADE",
            # ondelete: if project is deleted, this repo is invalidated.
        ),
        nullable=False,
        unique=True,
        doc="Project under version control"
        "Used as a working copy (WC) to produce/checkout snapshots.",
    ),
    sa.Column(
        "project_checksum",
        sa.String,
        nullable=False,
        doc="SHA-1 checksum of current working copy."
        "Used as a cache mechanism stored at 'modified'"
        "or to detect changes in state due to race conditions",
    ),
    sa.Column(
        "head_id",
        sa.BigInteger,
        sa.ForeignKey(
            "projects_vc_branches.id",
            name="fk_projects_vc_repos_head_id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=True,
        doc="Points to the last commit, known as HEAD in the git jargon"
        "Actually it points to the current branch that holds a head"
        "Null is used for detached head",
    ),
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        doc="Creation timestamp for this row",
    ),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp for last changes",
    ),
)


#
# COMMITS
#
#  - should NEVER be modified explicitly after creation
#
projects_vc_commits = sa.Table(
    "projects_vc_commits",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger,
        nullable=False,
        primary_key=True,
        doc="Global identifier throughout all repository's commits",
    ),
    sa.Column(
        "repo_id",
        sa.BigInteger,
        nullable=False,
        doc="Repository to which this commit belongs",
    ),
    sa.Column(
        "parent_commit_id",
        sa.BigInteger,
        sa.ForeignKey(
            "projects_vc_commits.id",
            name="fk_projects_vc_commits_parent_commit_id",
            onupdate="CASCADE",
        ),
        nullable=True,
        doc="Preceding commit",
    ),
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
            name="fk_projects_vc_commits_snapshot_uuid",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
        unique=True,
        doc="UUID of the project snapshot associated to this commit",
    ),
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp for this snapshot",
    ),
)


#
# head/TAGS
#

projects_vc_tags = sa.Table(
    "projects_vc_tags",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger,
        nullable=False,
        primary_key=True,
        doc="Global identifier throughout all repositories tags",
    ),
    sa.Column(
        "repo_id",
        sa.BigInteger,
        nullable=False,
        doc="Repository to which this commit belongs",
    ),
    sa.Column(
        "commit_id",
        sa.BigInteger,
        sa.ForeignKey(
            "projects_vc_commits.id",
            name="fk_projects_vc_tags_commit_id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=False,
        doc="Points to the tagged commit",
    ),
    sa.Column("name", sa.String, doc="Tag display name"),
    sa.Column("message", sa.String, doc="Commit message"),
    sa.Column(
        "hidden",
        sa.Boolean,
        doc="Skipped by default from tag listings."
        "Normally intended for internal use tags",
    ),
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        doc="Creation timestamp",
    ),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp for last changes",
    ),
    # CONSTRAINTS --------------
    sa.UniqueConstraint("name", "repo_id", name="repo_tag_uniqueness"),
)


#
# head/BRANCHES
#
projects_vc_branches = sa.Table(
    "projects_vc_branches",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger,
        nullable=False,
        primary_key=True,
        doc="Global identifier throughout all repositories branches",
    ),
    sa.Column(
        "repo_id",
        sa.BigInteger,
        nullable=False,
        doc="Repository to which this branch belongs",
    ),
    sa.Column(
        "head_id",
        sa.BigInteger,
        sa.ForeignKey(
            "projects_vc_commits.id",
            name="fk_projects_vc_branches_head_id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=False,
        doc="Points to the head commit of this branch",
    ),
    sa.Column("name", sa.String, doc="Branch display name"),
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        doc="Creation timestamp",
    ),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp for last changes",
    ),
    # CONSTRAINTS --------------
    sa.UniqueConstraint("name", "repo_id", name="repo_branch_uniqueness"),
)
