"""add use on demand clusters in comp_runs

Revision ID: 2cd329e47ea1
Revises: 763666c698fb
Create Date: 2023-09-04 06:57:51.291084+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2cd329e47ea1"
down_revision = "c4245e9e0f72"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "comp_runs", sa.Column("use_on_demand_clusters", sa.Boolean(), nullable=True)
    )
    # ### end Alembic commands ###
    op.execute(
        sa.DDL(
            "UPDATE comp_runs SET use_on_demand_clusters = false WHERE use_on_demand_clusters IS NULL"
        )
    )

    op.alter_column(
        "comp_runs",
        "use_on_demand_clusters",
        existing_type=sa.Boolean(),
        nullable=False,
    )


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("comp_runs", "use_on_demand_clusters")
    # ### end Alembic commands ###
