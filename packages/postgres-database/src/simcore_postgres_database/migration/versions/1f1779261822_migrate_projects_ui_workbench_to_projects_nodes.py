"""Migrate projects UI workbench to projects_nodes

Revision ID: 1f1779261822
Revises: 5f9749ff9007
Create Date: 2026-07-07 06:57:25.548358+00:00

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "1f1779261822"
down_revision = "5f9749ff9007"
branch_labels = None
depends_on = None

# Trigger that bumps projects_nodes.modified on every row change.
# The UI backfill below is not a real data change, so we disable it while
# backfilling to preserve each node's original `modified` timestamp.
_MODIFIED_TIMESTAMP_TRIGGER = "auto_update_modified_timestamp"


def upgrade():
    op.add_column(
        "projects_nodes",
        sa.Column(
            "ui",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )

    op.execute(sa.text(f"ALTER TABLE projects_nodes DISABLE TRIGGER {_MODIFIED_TIMESTAMP_TRIGGER}"))

    # Copy each per-node object from projects.ui.workbench into the matching projects_nodes.ui
    op.execute(
        sa.text(
            """
            UPDATE projects_nodes pn
            SET ui = p.ui -> 'workbench' -> pn.node_id
            FROM projects p
            WHERE pn.project_uuid = p.uuid
              AND jsonb_typeof(p.ui -> 'workbench') = 'object'
              AND (p.ui -> 'workbench') ? pn.node_id
              AND jsonb_typeof(p.ui -> 'workbench' -> pn.node_id) = 'object'
            """
        )
    )

    op.execute(sa.text(f"ALTER TABLE projects_nodes ENABLE TRIGGER {_MODIFIED_TIMESTAMP_TRIGGER}"))

    # Remove the now-migrated workbench key from projects.ui
    op.execute(
        sa.text(
            """
            UPDATE projects
            SET ui = ui - 'workbench'
            WHERE ui ? 'workbench'
            """
        )
    )


def downgrade():
    # Rebuild projects.ui.workbench from the non-empty projects_nodes.ui rows
    op.execute(
        sa.text(
            """
            UPDATE projects p
            SET ui = jsonb_set(
                COALESCE(p.ui, '{}'::jsonb),
                '{workbench}',
                (
                    SELECT jsonb_object_agg(pn.node_id, pn.ui)
                    FROM projects_nodes pn
                    WHERE pn.project_uuid = p.uuid AND pn.ui <> '{}'::jsonb
                )
            )
            WHERE EXISTS (
                SELECT 1
                FROM projects_nodes pn
                WHERE pn.project_uuid = p.uuid AND pn.ui <> '{}'::jsonb
            )
            """
        )
    )

    op.drop_column("projects_nodes", "ui")
