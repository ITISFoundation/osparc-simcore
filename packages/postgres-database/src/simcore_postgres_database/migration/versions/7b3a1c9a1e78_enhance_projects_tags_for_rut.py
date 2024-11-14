"""enhance projects_tags for RUT

Revision ID: 7b3a1c9a1e78
Revises: 8bfe65a5e294
Create Date: 2024-11-13 15:13:32.262499+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7b3a1c9a1e78"
down_revision = "8bfe65a5e294"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "projects_tags", sa.Column("project_uuid", sa.String(), nullable=False)
    )
    op.alter_column(
        "projects_tags", "project_id", existing_type=sa.BIGINT(), nullable=True
    )
    op.drop_constraint(
        "study_tags_study_id_tag_id_key", "projects_tags", type_="unique"
    )
    op.create_unique_constraint(None, "projects_tags", ["project_uuid", "tag_id"])
    op.drop_constraint("study_tags_study_id_fkey", "projects_tags", type_="foreignkey")
    op.create_foreign_key(
        None,
        "projects_tags",
        "projects",
        ["project_id"],
        ["id"],
        onupdate="CASCADE",
        ondelete="SET NULL",
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "projects_tags", type_="foreignkey")
    op.create_foreign_key(
        "study_tags_study_id_fkey",
        "projects_tags",
        "projects",
        ["project_id"],
        ["id"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )
    op.drop_constraint(None, "projects_tags", type_="unique")
    op.create_unique_constraint(
        "study_tags_study_id_tag_id_key", "projects_tags", ["project_id", "tag_id"]
    )
    op.alter_column(
        "projects_tags", "project_id", existing_type=sa.BIGINT(), nullable=False
    )
    op.drop_column("projects_tags", "project_uuid")
    # ### end Alembic commands ###
