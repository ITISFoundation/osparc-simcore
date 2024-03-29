"""adding node_uuid, instance, cpu/memory limits and indexes to resource tracker container table

Revision ID: 0cdf095b10fe
Revises: 52b5c2466605
Create Date: 2023-07-03 14:55:20.464906+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0cdf095b10fe"
down_revision = "52b5c2466605"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "resource_tracker_container",
        sa.Column("node_uuid", sa.String(), nullable=False),
    )
    op.add_column(
        "resource_tracker_container",
        sa.Column("node_label", sa.String(), nullable=True),
    )
    op.add_column(
        "resource_tracker_container", sa.Column("instance", sa.String(), nullable=True)
    )
    op.add_column(
        "resource_tracker_container",
        sa.Column("service_settings_limit_nano_cpus", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "resource_tracker_container",
        sa.Column(
            "service_settings_limit_memory_bytes", sa.BigInteger(), nullable=True
        ),
    )
    op.add_column(
        "resource_tracker_container",
        sa.Column("project_name", sa.String(), nullable=True),
    )
    op.add_column(
        "resource_tracker_container",
        sa.Column("user_email", sa.String(), nullable=True),
    )
    op.add_column(
        "resource_tracker_container",
        sa.Column("service_key", sa.String(), nullable=False),
    )
    op.add_column(
        "resource_tracker_container",
        sa.Column("service_version", sa.String(), nullable=False),
    )
    op.create_index(
        op.f("ix_resource_tracker_container_product_name"),
        "resource_tracker_container",
        ["product_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_tracker_container_prometheus_last_scraped"),
        "resource_tracker_container",
        ["prometheus_last_scraped"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_tracker_container_user_id"),
        "resource_tracker_container",
        ["user_id"],
        unique=False,
    )
    op.drop_column("resource_tracker_container", "image")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "resource_tracker_container",
        sa.Column("image", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
    op.drop_index(
        op.f("ix_resource_tracker_container_user_id"),
        table_name="resource_tracker_container",
    )
    op.drop_index(
        op.f("ix_resource_tracker_container_prometheus_last_scraped"),
        table_name="resource_tracker_container",
    )
    op.drop_index(
        op.f("ix_resource_tracker_container_product_name"),
        table_name="resource_tracker_container",
    )
    op.drop_column("resource_tracker_container", "service_version")
    op.drop_column("resource_tracker_container", "service_key")
    op.drop_column("resource_tracker_container", "user_email")
    op.drop_column("resource_tracker_container", "project_name")
    op.drop_column("resource_tracker_container", "service_settings_limit_memory_bytes")
    op.drop_column("resource_tracker_container", "service_settings_limit_nano_cpus")
    op.drop_column("resource_tracker_container", "instance")
    op.drop_column("resource_tracker_container", "node_label")
    op.drop_column("resource_tracker_container", "node_uuid")
    # ### end Alembic commands ###
