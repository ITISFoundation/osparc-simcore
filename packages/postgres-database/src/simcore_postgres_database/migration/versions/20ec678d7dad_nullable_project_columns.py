"""Nullable project columns

Revision ID: 20ec678d7dad
Revises: 99db5efc4548
Create Date: 2019-07-04 08:44:35.901118+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20ec678d7dad"
down_revision = "99db5efc4548"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "projects", "description", existing_type=sa.VARCHAR(), nullable=True
    )
    op.alter_column("projects", "thumbnail", existing_type=sa.VARCHAR(), nullable=True)
    # ### end Alembic commands ###


from simcore_postgres_database.models.projects import projects


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute(
        sa.update(projects).where(projects.c.thumbnail is None).values(thumbnail="")
    )
    op.alter_column("projects", "thumbnail", existing_type=sa.VARCHAR(), nullable=False)

    op.execute(
        sa.update(projects).where(projects.c.description is None).values(description="")
    )
    op.alter_column(
        "projects", "description", existing_type=sa.VARCHAR(), nullable=False
    )
    # ### end Alembic commands ###
