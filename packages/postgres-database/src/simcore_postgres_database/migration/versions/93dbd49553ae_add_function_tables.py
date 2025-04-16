"""Add function tables

Revision ID: 93dbd49553ae
Revises: cf8f743fd0b7
Create Date: 2025-04-16 09:32:48.976846+00:00

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "93dbd49553ae"
down_revision = "cf8f743fd0b7"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "function_job_collections",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("uuid", name="function_job_collections_pk"),
    )
    op.create_index(
        op.f("ix_function_job_collections_uuid"),
        "function_job_collections",
        ["uuid"],
        unique=False,
    )
    op.create_table(
        "functions",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("function_class", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("input_schema", sa.JSON(), nullable=True),
        sa.Column("output_schema", sa.JSON(), nullable=True),
        sa.Column("system_tags", sa.JSON(), nullable=True),
        sa.Column("user_tags", sa.JSON(), nullable=True),
        sa.Column("class_specific_data", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("uuid", name="functions_pk"),
    )
    op.create_index(op.f("ix_functions_uuid"), "functions", ["uuid"], unique=False)
    op.create_table(
        "function_jobs",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("function_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("function_class", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("inputs", sa.JSON(), nullable=True),
        sa.Column("outputs", sa.JSON(), nullable=True),
        sa.Column("class_specific_data", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["function_uuid"],
            ["functions.uuid"],
            name="fk_functions_to_function_jobs_to_function_uuid",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uuid", name="function_jobs_pk"),
    )
    op.create_index(
        op.f("ix_function_jobs_function_uuid"),
        "function_jobs",
        ["function_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_function_jobs_uuid"), "function_jobs", ["uuid"], unique=False
    )
    op.create_table(
        "function_job_collections_to_function_jobs",
        sa.Column(
            "function_job_collection_uuid", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("function_job_uuid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["function_job_collection_uuid"],
            ["function_job_collections.uuid"],
            name="fk_func_job_coll_to_func_jobs_to_func_job_coll_uuid",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["function_job_uuid"],
            ["function_jobs.uuid"],
            name="fk_func_job_coll_to_func_jobs_to_func_job_uuid",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )
    op.drop_index("idx_projects_last_change_date_desc", table_name="projects")
    op.create_index(
        "idx_projects_last_change_date_desc",
        "projects",
        ["last_change_date"],
        unique=False,
        postgresql_using="btree",
        postgresql_ops={"last_change_date": "DESC"},
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        "idx_projects_last_change_date_desc",
        table_name="projects",
        postgresql_using="btree",
        postgresql_ops={"last_change_date": "DESC"},
    )
    op.create_index(
        "idx_projects_last_change_date_desc",
        "projects",
        [sa.text("last_change_date DESC")],
        unique=False,
    )
    op.drop_table("function_job_collections_to_function_jobs")
    op.drop_index(op.f("ix_function_jobs_uuid"), table_name="function_jobs")
    op.drop_index(op.f("ix_function_jobs_function_uuid"), table_name="function_jobs")
    op.drop_table("function_jobs")
    op.drop_index(op.f("ix_functions_uuid"), table_name="functions")
    op.drop_table("functions")
    op.drop_index(
        op.f("ix_function_job_collections_uuid"), table_name="function_job_collections"
    )
    op.drop_table("function_job_collections")
    # ### end Alembic commands ###
