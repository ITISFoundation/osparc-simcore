#
# TODO: create template to produce these tables over another table other than project
#

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ._common import RefActions
from .base import metadata
from .projects import projects

# REPOSITORES
#
# Projects under version-control are assigned a repository
#   - keeps information of the current branch to recover HEAD ref
#   - when repo is deleted, all project_vc_* get deleted
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
            projects.c.uuid,
            name="fk_projects_vc_repos_project_uuid",
            ondelete=RefActions.CASCADE,  # if project is deleted, all references in project_vc_* tables are deleted except for projects_vc_snapshots.
            onupdate=RefActions.CASCADE,
        ),
        nullable=False,
        unique=True,
        doc="Project under version control"
        "Used as a working copy (WC) to produce/checkout snapshots.",
    ),
    sa.Column(
        "project_checksum",
        sa.String,
        nullable=True,
        doc="SHA-1 checksum of current working copy."
        "Used as a cache mechanism stored at 'modified'"
        "or to detect changes in state due to race conditions",
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


projects_vc_snapshots = sa.Table(
    "projects_vc_snapshots",
    metadata,
    sa.Column(
        "checksum",
        sa.String,
        primary_key=True,
        nullable=False,
        doc="SHA-1 checksum of snapshot."
        "The columns projects_vc_repos.project_checksum and projects_vc_repos.snapshot_checksum "
        "are both checksums of the same entity (i.e. a project) in two different states, "
        "namely the project's WC and some snapshot respectively.",
    ),
    sa.Column(
        "content",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="snapshot content",
    ),
)


#
# COMMITS
#
#  - should NEVER be modified explicitly after creation
#  - commits are inter-related. WARNING with deletion
#
# SEE https://git-scm.com/book/en/v2/Git-Internals-Git-References

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
        sa.ForeignKey(
            projects_vc_repos.c.id,
            name="fk_projects_vc_commits_repo_id",
            ondelete=RefActions.CASCADE,
            onupdate=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Repository to which this commit belongs",
    ),
    sa.Column(
        "parent_commit_id",
        sa.BigInteger,
        sa.ForeignKey(
            "projects_vc_commits.id",
            name="fk_projects_vc_commits_parent_commit_id",
            onupdate=RefActions.CASCADE,
        ),
        nullable=True,
        doc="Preceding commit",
    ),
    sa.Column(
        "snapshot_checksum",
        sa.String,
        sa.ForeignKey(
            projects_vc_snapshots.c.checksum,
            name="fk_projects_vc_commits_snapshot_checksum",
            ondelete=RefActions.RESTRICT,
            onupdate=RefActions.CASCADE,
        ),
        nullable=False,
        doc="SHA-1 checksum of snapshot."
        "Used as revision/commit identifier since it is unique per repo",
    ),
    sa.Column("message", sa.String, doc="Commit message"),
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
# SEE https://git-scm.com/book/en/v2/Git-Internals-Git-References

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
        sa.ForeignKey(
            projects_vc_repos.c.id,
            name="fk_projects_vc_tags_repo_id",
            ondelete=RefActions.CASCADE,
            onupdate=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Repository to which this commit belongs",
    ),
    sa.Column(
        "commit_id",
        sa.BigInteger,
        sa.ForeignKey(
            projects_vc_commits.c.id,
            name="fk_projects_vc_tags_commit_id",
            ondelete=RefActions.CASCADE,
            onupdate=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Points to the tagged commit",
    ),
    sa.Column("name", sa.String, doc="Tag display name"),
    sa.Column("message", sa.String, doc="Tag annotation"),
    sa.Column(
        "hidden",
        sa.Boolean,
        default=False,
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
# SEE https://git-scm.com/book/en/v2/Git-Internals-Git-References

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
        sa.ForeignKey(
            projects_vc_repos.c.id,
            name="projects_vc_branches_repo_id",
            ondelete=RefActions.CASCADE,
            onupdate=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Repository to which this branch belongs",
    ),
    sa.Column(
        "head_commit_id",
        sa.BigInteger,
        sa.ForeignKey(
            projects_vc_commits.c.id,
            name="fk_projects_vc_branches_head_commit_id",
            ondelete=RefActions.RESTRICT,
            onupdate=RefActions.CASCADE,
        ),
        nullable=True,
        doc="Points to the head commit of this branchNull heads are detached",
    ),
    sa.Column("name", sa.String, default="main", doc="Branch display name"),
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


#
# HEADS
#
#  - the last commit in a given repo, also called the HEAD reference
#  - added in an association table to avoid circular dependency between projects_vc_repos and  projects_vc_branches
#
# SEE https://git-scm.com/book/en/v2/Git-Internals-Git-References

projects_vc_heads = sa.Table(
    "projects_vc_heads",
    metadata,
    sa.Column(
        "repo_id",
        sa.BigInteger,
        sa.ForeignKey(
            projects_vc_repos.c.id,
            name="projects_vc_branches_repo_id",
            ondelete=RefActions.CASCADE,
            onupdate=RefActions.CASCADE,
        ),
        primary_key=True,
        nullable=False,
        doc="Repository to which this branch belongs",
    ),
    sa.Column(
        "head_branch_id",
        sa.BigInteger,
        sa.ForeignKey(
            projects_vc_branches.c.id,
            name="fk_projects_vc_heads_head_branch_id",
            ondelete=RefActions.CASCADE,
            onupdate=RefActions.CASCADE,
        ),
        unique=True,
        nullable=True,
        doc="Points to the current branch that holds the HEAD"
        "Null is used for detached head",
    ),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp for last changes on head branch",
    ),
)
