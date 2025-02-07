"""drop projects_version_control

Revision ID: 061607911a22
Revises: 611f956aa3e3
Create Date: 2025-02-06 19:28:49.918139+00:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "061607911a22"
down_revision = "611f956aa3e3"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("projects_vc_heads")
    op.drop_table("projects_vc_branches")
    op.drop_table("projects_vc_tags")
    op.drop_table("projects_vc_commits")
    op.drop_table("projects_vc_snapshots")
    op.drop_table("projects_vc_repos")


def downgrade():

    op.create_table(
        "projects_vc_snapshots",
        sa.Column("checksum", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column(
            "content",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            autoincrement=False,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("checksum", name="projects_vc_snapshots_pkey"),
        postgresql_ignore_search_path=False,
    )

    op.create_table(
        "projects_vc_repos",
        sa.Column(
            "id",
            sa.BIGINT(),
            server_default=sa.text("nextval('projects_vc_repos_id_seq'::regclass)"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("project_uuid", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("project_checksum", sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column(
            "created",
            postgresql.TIMESTAMP(),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "modified",
            postgresql.TIMESTAMP(),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_uuid"],
            ["projects.uuid"],
            name="fk_projects_vc_repos_project_uuid",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="projects_vc_repos_pkey"),
        sa.UniqueConstraint("project_uuid", name="projects_vc_repos_project_uuid_key"),
        postgresql_ignore_search_path=False,
    )

    op.create_table(
        "projects_vc_commits",
        sa.Column(
            "id",
            sa.BIGINT(),
            server_default=sa.text("nextval('projects_vc_commits_id_seq'::regclass)"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("repo_id", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("parent_commit_id", sa.BIGINT(), autoincrement=False, nullable=True),
        sa.Column(
            "snapshot_checksum", sa.VARCHAR(), autoincrement=False, nullable=False
        ),
        sa.Column("message", sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column(
            "created",
            postgresql.TIMESTAMP(),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["parent_commit_id"],
            ["projects_vc_commits.id"],
            name="fk_projects_vc_commits_parent_commit_id",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repo_id"],
            ["projects_vc_repos.id"],
            name="fk_projects_vc_commits_repo_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_checksum"],
            ["projects_vc_snapshots.checksum"],
            name="fk_projects_vc_commits_snapshot_checksum",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="projects_vc_commits_pkey"),
        postgresql_ignore_search_path=False,
    )

    op.create_table(
        "projects_vc_branches",
        sa.Column("id", sa.BIGINT(), autoincrement=True, nullable=False),
        sa.Column("repo_id", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("head_commit_id", sa.BIGINT(), autoincrement=False, nullable=True),
        sa.Column("name", sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column(
            "created",
            postgresql.TIMESTAMP(),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "modified",
            postgresql.TIMESTAMP(),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["head_commit_id"],
            ["projects_vc_commits.id"],
            name="fk_projects_vc_branches_head_commit_id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["repo_id"],
            ["projects_vc_repos.id"],
            name="projects_vc_branches_repo_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="projects_vc_branches_pkey"),
        sa.UniqueConstraint("name", "repo_id", name="repo_branch_uniqueness"),
    )

    op.create_table(
        "projects_vc_tags",
        sa.Column("id", sa.BIGINT(), autoincrement=True, nullable=False),
        sa.Column("repo_id", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("commit_id", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("name", sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column("message", sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column("hidden", sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.Column(
            "created",
            postgresql.TIMESTAMP(),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "modified",
            postgresql.TIMESTAMP(),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["commit_id"],
            ["projects_vc_commits.id"],
            name="fk_projects_vc_tags_commit_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repo_id"],
            ["projects_vc_repos.id"],
            name="fk_projects_vc_tags_repo_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="projects_vc_tags_pkey"),
        sa.UniqueConstraint("name", "repo_id", name="repo_tag_uniqueness"),
    )

    op.create_table(
        "projects_vc_heads",
        sa.Column("repo_id", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("head_branch_id", sa.BIGINT(), autoincrement=False, nullable=True),
        sa.Column(
            "modified",
            postgresql.TIMESTAMP(),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["head_branch_id"],
            ["projects_vc_branches.id"],
            name="fk_projects_vc_heads_head_branch_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repo_id"],
            ["projects_vc_repos.id"],
            name="projects_vc_branches_repo_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("repo_id", name="projects_vc_heads_pkey"),
        sa.UniqueConstraint(
            "head_branch_id", name="projects_vc_heads_head_branch_id_key"
        ),
    )
