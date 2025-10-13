"""add order to function job collections

Revision ID: 06596ce2bc3e
Revises: 9dddb16914a4
Create Date: 2025-10-08 13:54:39.943703+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "06596ce2bc3e"
down_revision = "9dddb16914a4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "funcapi_function_job_collections_to_function_jobs",
        sa.Column("order", sa.Integer(), default=0, nullable=True),
    )
    # Set the "order" column so that it restarts from 1 for each collection_id,
    # ordering by function_job_id within each collection
    op.execute(
        sa.text(
            """
            UPDATE funcapi_function_job_collections_to_function_jobs
            SET "order" = sub.row_number
            FROM (
                SELECT function_job_collection_uuid, function_job_uuid,
                       ROW_NUMBER() OVER (PARTITION BY function_job_collection_uuid) AS row_number
                FROM funcapi_function_job_collections_to_function_jobs
            ) AS sub
            WHERE funcapi_function_job_collections_to_function_jobs.function_job_collection_uuid = sub.function_job_collection_uuid
              AND funcapi_function_job_collections_to_function_jobs.function_job_uuid = sub.function_job_uuid
            """
        )
    )
    op.drop_constraint(
        "funcapi_function_job_collections_to_function_jobs_pk",
        "funcapi_function_job_collections_to_function_jobs",
        type_="primary",
    )
    op.create_primary_key(
        "funcapi_function_job_collections_to_function_jobs_pk",
        "funcapi_function_job_collections_to_function_jobs",
        ["function_job_collection_uuid", "order"],
    )
    op.alter_column(
        "funcapi_function_job_collections_to_function_jobs",
        "order",
        existing_type=sa.Integer(),
        nullable=False,
    )
    # ### end Alembic commands ###


def downgrade():
    op.drop_constraint(
        "funcapi_function_job_collections_to_function_jobs_pk",
        "funcapi_function_job_collections_to_function_jobs",
        type_="primary",
    )
    op.create_primary_key(
        "funcapi_function_job_collections_to_function_jobs_pk",
        "funcapi_function_job_collections_to_function_jobs",
        ["function_job_collection_uuid", "function_job_uuid"],
    )

    op.drop_column("funcapi_function_job_collections_to_function_jobs", "order")
    # ### end Alembic commands ###
