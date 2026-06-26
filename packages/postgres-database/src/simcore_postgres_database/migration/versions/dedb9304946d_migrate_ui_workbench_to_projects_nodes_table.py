"""Migrate UI workbench to projects_nodes table

Revision ID: dedb9304946d
Revises: c9c165644731
Create Date: 2026-06-26 13:33:52.603161+00:00

"""

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "dedb9304946d"
down_revision = "c9c165644731"
branch_labels = None
depends_on = None


def _migrate_ui_workbench_to_projects_nodes() -> None:
    """Copy per-node UI from ``projects.ui->'workbench'`` into ``projects_nodes.ui``.

    Only the ``workbench`` entry of the ``projects.ui`` JSON is read; the column
    and its other root fields are left untouched. For each node (keyed by uuid)
    the value is written into the ``ui`` column of the matching projects_nodes row.
    """
    connection = op.get_bind()

    projects_with_ui_workbench = connection.execute(
        sa.text(
            """
            SELECT uuid, ui -> 'workbench' AS workbench_ui
            FROM projects
            WHERE ui ? 'workbench'
              AND jsonb_typeof(ui -> 'workbench') = 'object'
            """
        )
    )

    for project_uuid, workbench_ui in projects_with_ui_workbench:
        if not workbench_ui:
            continue

        for node_id, node_ui in workbench_ui.items():
            if not node_ui:
                continue
            connection.execute(
                sa.text(
                    """
                    UPDATE projects_nodes
                    SET ui = :node_ui
                    WHERE project_uuid = :project_uuid
                      AND node_id = :node_id
                    """
                ),
                {
                    "project_uuid": project_uuid,
                    "node_id": node_id,
                    "node_ui": json.dumps(node_ui),
                },
            )


def upgrade():
    op.add_column(
        "projects_nodes",
        sa.Column(
            "ui",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Front-end per-node UI state (e.g. position, marker). "
            "Replaces the per-node entries previously stored in projects.ui.workbench",
        ),
    )

    _migrate_ui_workbench_to_projects_nodes()


def downgrade():
    op.drop_column("projects_nodes", "ui")
