"""project_nodes modification + creation projects_node_to_pricing_unit

Revision ID: 57ab8c419ca6
Revises: b102946c8134
Create Date: 2023-10-05 18:26:26.018893+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "57ab8c419ca6"
down_revision = "b102946c8134"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE projects_nodes DROP CONSTRAINT projects_nodes_pkey")
    op.execute(
        "ALTER TABLE projects_nodes ADD COLUMN project_node_id SERIAL PRIMARY KEY"
    )
    op.execute(
        "ALTER TABLE projects_nodes ADD CONSTRAINT projects_nodes__node_project UNIQUE (node_id, project_uuid)"
    )

    op.create_index(
        op.f("ix_projects_nodes_node_id"), "projects_nodes", ["node_id"], unique=False
    )
    op.create_index(
        op.f("ix_projects_nodes_project_uuid"),
        "projects_nodes",
        ["project_uuid"],
        unique=False,
    )

    op.create_table(
        "projects_node_to_pricing_unit",
        sa.Column("project_node_id", sa.BigInteger(), nullable=False),
        sa.Column("pricing_plan_id", sa.BigInteger(), nullable=False),
        sa.Column("pricing_unit_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "modified",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_node_id"],
            ["projects_nodes.project_node_id"],
            name="fk_projects_nodes__project_node_to_pricing_unit__uuid",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("project_node_id"),
    )


def downgrade():
    op.drop_table("projects_node_to_pricing_unit")

    op.drop_index(op.f("ix_projects_nodes_project_uuid"), table_name="projects_nodes")
    op.drop_index(op.f("ix_projects_nodes_node_id"), table_name="projects_nodes")

    op.execute("ALTER TABLE projects_nodes DROP CONSTRAINT projects_nodes_pkey")
    op.execute(
        "ALTER TABLE projects_nodes DROP CONSTRAINT projects_nodes__node_project"
    )
    op.execute("ALTER TABLE projects_nodes ADD PRIMARY KEY (node_id, project_uuid)")
