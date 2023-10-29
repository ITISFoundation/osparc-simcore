"""resource_tracker_service_runs helpers for missing heartbeat

Revision ID: 22404057a50c
Revises: 2a4b4167e088
Create Date: 2023-10-25 19:17:29.928871+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "22404057a50c"
down_revision = "2a4b4167e088"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "resource_tracker_service_runs",
        sa.Column("service_run_status_msg", sa.String(), nullable=True),
    )
    op.add_column(
        "resource_tracker_service_runs",
        sa.Column("missed_heartbeat_counter", sa.SmallInteger(), nullable=False),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("resource_tracker_service_runs", "missed_heartbeat_counter")
    op.drop_column("resource_tracker_service_runs", "service_run_status_msg")
    # ### end Alembic commands ###
