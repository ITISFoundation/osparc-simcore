"""migrate projects workbench step1

Revision ID: add0afaaf728
Revises: 6e91067932f2
Create Date: 2023-06-22 14:45:38.827559+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add0afaaf728"
down_revision = "6e91067932f2"
branch_labels = None
depends_on = None


def upgrade():
    projects_table = sa.table(
        "projects",
        sa.column("uuid"),
        sa.column("workbench"),
        sa.column("creation_date"),
        sa.column("last_change_date"),
    )
    projects_nodes_table = sa.table(
        "projects_nodes",
        sa.column("project_uuid"),
        sa.column("node_id"),
        sa.column("created"),
        sa.column("modified"),
    )

    connection = op.get_bind()

    for project_uuid, workbench, creation_date, last_change_date in connection.execute(
        projects_table.select()
    ):
        for node_id in workbench.keys():
            connection.execute(
                projects_nodes_table.insert().values(
                    project_uuid=project_uuid,
                    node_id=node_id,
                    created=creation_date,
                    modified=last_change_date,
                )
            )


def downgrade():
    projects_nodes_table = sa.table(
        "projects_nodes",
        sa.column("project_uuid"),
        sa.column("node_id"),
    )
    connection = op.get_bind()

    connection.execute(projects_nodes_table.delete())
