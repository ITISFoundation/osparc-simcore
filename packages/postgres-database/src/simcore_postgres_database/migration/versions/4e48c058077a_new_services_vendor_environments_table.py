"""new services_vendor_environments table

Revision ID: 4e48c058077a
Revises: 0c084cb1091c
Create Date: 2023-05-18 10:48:19.234075+00:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "4e48c058077a"
down_revision = "0c084cb1091c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "services_vendor_environments",
        sa.Column("service_key", sa.String(), nullable=False),
        sa.Column(
            "identifiers_map",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "modified", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint(
            "service_key", name="services_vendor_environments_service_key_pk"
        ),
    )
    op.create_unique_constraint(
        "services_specifications_service_key_unique",
        "services_specifications",
        ["service_key"],
    )


def downgrade():
    op.drop_constraint(
        "services_specifications_service_key_unique",
        "services_specifications",
        type_="unique",
    )
    op.drop_table("services_vendor_environments")
