"""Adds trashed by column

Revision ID: f19905923355
Revises: 307017ee1a49
Create Date: 2025-01-10 16:43:21.559138+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f19905923355"
down_revision = "307017ee1a49"
branch_labels = None
depends_on = None


def upgrade():

    with op.batch_alter_table("folders_v2") as batch_op:
        batch_op.alter_column(
            "trashed_at",
            new_column_name="trashed",
            comment="The date and time when the folders was marked as trashed. Null if the folders has not been trashed [default].",
        )
        batch_op.add_column(
            sa.Column(
                "trashed_by",
                sa.BigInteger(),
                nullable=True,
                comment="User who trashed the folders, or null if not trashed or user is unknown.",
            )
        )
        batch_op.create_foreign_key(
            "fk_folders_trashed_by_user_id",
            "users",
            ["trashed_by"],
            ["id"],
            onupdate="CASCADE",
            ondelete="SET NULL",
        )

    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column(
            "trashed_at",
            new_column_name="trashed",
            comment="The date and time when the projects was marked as trashed. Null if the projects has not been trashed [default].",
        )
        batch_op.add_column(
            sa.Column(
                "trashed_by",
                sa.BigInteger(),
                nullable=True,
                comment="User who trashed the projects, or null if not trashed or user is unknown.",
            )
        )
        batch_op.create_foreign_key(
            "fk_projects_trashed_by_user_id",
            "users",
            ["trashed_by"],
            ["id"],
            onupdate="CASCADE",
            ondelete="SET NULL",
        )


def downgrade():
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_constraint("fk_projects_trashed_by_user_id", type_="foreignkey")
        batch_op.drop_column("trashed_by")
        batch_op.alter_column(
            "trashed",
            new_column_name="trashed_at",
            comment="The date and time when the project was marked as trashed. Null if the project has not been trashed [default].",
        )

    with op.batch_alter_table("folders_v2") as batch_op:
        batch_op.drop_constraint("fk_folders_trashed_by_user_id", type_="foreignkey")
        batch_op.drop_column("trashed_by")
        batch_op.alter_column(
            "trashed",
            new_column_name="trashed_at",
            comment="The date and time when the folder was marked as trashed. Null if the folder has not been trashed [default].",
        )
