"""Remove user_to_projects table

Revision ID: 66969aad0315
Revises: 066e6a93b741
Create Date: 2026-07-13 20:02:53.544354+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "66969aad0315"
down_revision = "066e6a93b741"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("user_to_projects")


def downgrade():
    op.create_table(
        "user_to_projects",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_user_to_projects_id_projects",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_to_projects_id_users",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="user_to_projects_pkey"),
    )
