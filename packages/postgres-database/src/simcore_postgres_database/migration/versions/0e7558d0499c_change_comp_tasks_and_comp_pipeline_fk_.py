"""change comp_tasks and comp_pipeline fk to reference projects

Revision ID: 0e7558d0499c
Revises: 4ec498d70da6
Create Date: 2026-07-21 08:06:08.785690+00:00

NOTE: rows in comp_tasks/comp_pipeline whose project_id has no matching
projects.uuid are deleted during upgrade() to satisfy the new foreign key
constraints. This data loss cannot be undone by downgrade().
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0e7558d0499c"
down_revision = "4ec498d70da6"
branch_labels = None
depends_on = None


def upgrade():
    # remove orphaned rows that would violate the new foreign keys
    op.execute(
        "DELETE FROM comp_tasks WHERE project_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM projects WHERE projects.uuid = comp_tasks.project_id)"
    )

    # comp_tasks.project_id used to reference comp_pipeline.project_id, now references projects.uuid
    op.drop_constraint(op.f("comp_tasks_project_id_fkey"), "comp_tasks", type_="foreignkey")
    op.create_foreign_key(
        "fk_comp_tasks_project_id_projects",
        "comp_tasks",
        "projects",
        ["project_id"],
        ["uuid"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )

    # comp_pipeline.project_id had no foreign key at all; add one now that
    # comp_tasks no longer references comp_pipeline (safe to delete orphans)
    op.execute(
        "DELETE FROM comp_pipeline WHERE "
        "NOT EXISTS (SELECT 1 FROM projects WHERE projects.uuid = comp_pipeline.project_id)"
    )
    op.create_foreign_key(
        "fk_comp_pipeline_project_id_projects",
        "comp_pipeline",
        "projects",
        ["project_id"],
        ["uuid"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint("fk_comp_pipeline_project_id_projects", "comp_pipeline", type_="foreignkey")

    op.drop_constraint("fk_comp_tasks_project_id_projects", "comp_tasks", type_="foreignkey")
    op.create_foreign_key(
        op.f("comp_tasks_project_id_fkey"),
        "comp_tasks",
        "comp_pipeline",
        ["project_id"],
        ["project_id"],
    )
